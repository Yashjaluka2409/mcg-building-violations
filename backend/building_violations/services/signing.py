"""
Digital signature of notice PDFs (PAdES, embedded in the PDF - opens as "signed" in Adobe Reader).

Backends (settings.BVMS_SIGNER["BACKEND"]):
  local   - PKCS#12 certificate file (.p12). For UAT a self-signed certificate is generated on first
            use (`ensure_dev_certificate`). In production put the MCG organisational DSC / document
            signer certificate here (Class-3 Document Signer certificate issued to "Municipal
            Corporation Gurugram" is the recommended CCA-compliant approach for bulk server signing).
  pkcs11  - USB DSC token attached to the signing server (officer's Class-3 DSC).
  esign   - Aadhaar eSign (ASP integration: the JC authenticates with Aadhaar OTP at issue time).
            The transport is provider-specific; `ESignSigner.sign` shows the contract to implement.

Independently of the PAdES signature, every notice carries a SHA-256 hash and a verification code
in its QR code, so anybody can verify a printed copy on the public verification page.
"""
from __future__ import annotations

import datetime as dt
import io
import logging
from pathlib import Path

from django.conf import settings

log = logging.getLogger(__name__)


class SignResult:
    def __init__(self, ok: bool, pdf: bytes | None = None, signer_name: str = "", subject: str = "", serial: str = "", error: str = ""):
        self.ok, self.pdf, self.signer_name, self.subject, self.serial, self.error = ok, pdf, signer_name, subject, serial, error


def ensure_dev_certificate(p12_path: Path, password: str) -> Path:
    """Create a self-signed PKCS#12 for development/UAT if none exists."""
    if p12_path.exists():
        return p12_path
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives.serialization import pkcs12
    from cryptography.x509.oid import NameOID

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, "IN"),
        x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "Haryana"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Municipal Corporation Gurugram"),
        x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, "Building Violation Management System (UAT)"),
        x509.NameAttribute(NameOID.COMMON_NAME, "MCG BVMS Document Signer (TEST - NOT FOR PRODUCTION)"),
    ])
    now = dt.datetime.now(dt.timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
            .serial_number(x509.random_serial_number()).not_valid_before(now - dt.timedelta(days=1))
            .not_valid_after(now + dt.timedelta(days=365 * 3))
            .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
            .add_extension(x509.KeyUsage(digital_signature=True, content_commitment=True, key_encipherment=False,
                                         data_encipherment=False, key_agreement=False, key_cert_sign=False,
                                         crl_sign=False, encipher_only=False, decipher_only=False), critical=True)
            .sign(key, hashes.SHA256()))
    p12 = pkcs12.serialize_key_and_certificates(b"mcg-bvms", key, cert, None,
                                                serialization.BestAvailableEncryption(password.encode()))
    p12_path.parent.mkdir(parents=True, exist_ok=True)
    p12_path.write_bytes(p12)
    log.warning("Generated self-signed development signer certificate at %s", p12_path)
    return p12_path


class LocalP12Signer:
    def __init__(self):
        cfg = settings.BVMS_SIGNER
        self.path = Path(cfg["P12_PATH"])
        self.password = cfg["P12_PASSWORD"]

    def sign(self, pdf_bytes: bytes, reason: str, signer_name: str, location: str = "Gurugram") -> SignResult:
        try:
            from pyhanko.sign import signers
            from pyhanko.sign.fields import SigFieldSpec
            from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
            from pyhanko.sign.signers.pdf_signer import PdfSigner, PdfSignatureMetadata
            from pyhanko import stamp
            from pyhanko.pdf_utils import text

            ensure_dev_certificate(self.path, self.password)
            signer = signers.SimpleSigner.load_pkcs12(pfx_file=str(self.path), passphrase=self.password.encode())
            if signer is None:
                return SignResult(False, error="Could not load PKCS#12 signer")
            cert = signer.signing_cert
            subject = cert.subject.human_friendly
            serial = str(cert.serial_number)
            meta = PdfSignatureMetadata(field_name="MCG_BVMS_Signature", reason=reason, location=location, name=signer_name)
            w = IncrementalPdfFileWriter(io.BytesIO(pdf_bytes))
            # visible signature box at the bottom-right of the last page
            n_pages = len(w.root["/Pages"]["/Kids"]) if "/Kids" in w.root["/Pages"] else 1
            spec = SigFieldSpec(sig_field_name="MCG_BVMS_Signature", on_page=max(n_pages - 1, 0), box=(340, 40, 560, 110))
            style = stamp.TextStampStyle(stamp_text=f"Digitally signed by\n%(signer)s\nDate: %(ts)s\nReason: {reason[:40]}",
                                         text_box_style=text.TextBoxStyle(font_size=7), border_width=1)
            pdf_signer = PdfSigner(meta, signer=signer, stamp_style=style, new_field_spec=spec)
            out = io.BytesIO()
            pdf_signer.sign_pdf(w, output=out)
            return SignResult(True, pdf=out.getvalue(), signer_name=signer_name, subject=subject, serial=serial)
        except Exception as exc:
            log.exception("PDF signing failed")
            return SignResult(False, error=str(exc))


class PKCS11Signer(LocalP12Signer):
    """USB token / HSM signer. Requires the vendor PKCS#11 library path (e.g. eToken, WD ProxKey)."""
    def sign(self, pdf_bytes, reason, signer_name, location="Gurugram"):
        cfg = settings.BVMS_SIGNER
        try:
            from pyhanko.sign import pkcs11 as p11
            from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
            from pyhanko.sign.signers.pdf_signer import PdfSigner, PdfSignatureMetadata
            with p11.PKCS11SigningContext(cfg["PKCS11_LIB"], slot_no=int(cfg["PKCS11_SLOT"] or 0), user_pin=cfg.get("P12_PASSWORD")) as signer:
                w = IncrementalPdfFileWriter(io.BytesIO(pdf_bytes))
                out = io.BytesIO()
                PdfSigner(PdfSignatureMetadata(field_name="MCG_BVMS_Signature", reason=reason, location=location, name=signer_name), signer=signer).sign_pdf(w, output=out)
                return SignResult(True, pdf=out.getvalue(), signer_name=signer_name, subject=signer.signing_cert.subject.human_friendly, serial=str(signer.signing_cert.serial_number))
        except Exception as exc:
            return SignResult(False, error=str(exc))


class ESignSigner:
    """Aadhaar eSign (CCA-empanelled ASP). Implement `sign` against the ASP's API: hash the PDF
    (SHA-256, PAdES ByteRange), send the eSign XML request with the officer's Aadhaar OTP/biometric
    response, receive the PKCS#7 signature and embed it with pyHanko's external-signing flow."""
    def sign(self, pdf_bytes, reason, signer_name, location="Gurugram"):
        return SignResult(False, error="Aadhaar eSign ASP integration not configured (see services/signing.py)")


def get_signer():
    backend = settings.BVMS_SIGNER.get("BACKEND", "local")
    return {"local": LocalP12Signer, "pkcs11": PKCS11Signer, "esign": ESignSigner}.get(backend, LocalP12Signer)()
