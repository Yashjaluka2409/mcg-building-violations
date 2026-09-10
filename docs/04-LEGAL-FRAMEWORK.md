# 04 - Legal Framework of the Building Violation Management System

This document is generated from `shared/legal/legal_sections.json` and `shared/legal/violation_catalogue.json` (run `python3 shared/legal/generate_catalogue.py`). Those JSON files are loaded into the database by `manage.py load_legal_catalogue` and drive the violation picker, the notice templates and the statutory timers of the workflow.

> **Verification note.** Statutory text was extracted from scanned PDFs (docs/legal-sources/) and cleaned by hand. Sections flagged *verify* below must be checked by the Legal Branch against the Gazette before notices are relied upon in court. Sections 261 (appeal to Divisional Commissioner - Act 1 of 2007), 263A (Act 12 of 2013) and 408A-408C (competent authority = Joint Commissioner, s.2(4A)) are the provisions the workflow is built on.

## 1. Statutes relied upon

| Code | Statute | Citation | Used for |
|---|---|---|---|
| HMCA1994 | Haryana Municipal Corporation Act, 1994 | Haryana Act No. 16 of 1994 (as amended, incl. Act 1 of 2007 and Act 12 of 2013) | Municipal Corporation of Gurugram |
| HBC2017 | Haryana Building Code, 2017 | Notification No. Misc-138A-Loose/7/5/2006-2TCP dated 29.03.2017, with amendments up to 25.05.2023 | Whole of Haryana (building plan sanction, deviations, OC) |
| HPPA1972 | Haryana Public Premises and Land (Eviction and Rent Recovery) Act, 1972 | Haryana Act No. 24 of 1972 | Government / local-authority land (Collector route) |
| PSRCA1963 | Punjab Scheduled Roads and Controlled Areas Restriction of Unregulated Development Act, 1963 | Punjab Act 41 of 1963 (as applicable to Haryana) | Controlled areas / scheduled roads (DTCP route) |
| BNS2023 | Bharatiya Nyaya Sanhita, 2023 | Act 45 of 2023 | Criminal consequences quoted in orders |

## 2. How the law is mapped to the workflow


| Stage in the system | Legal basis | Statutory time limit enforced by the software |
|---|---|---|
| Field inspection, geotagged evidence | s.372/entry powers of the Commissioner; s.403 (certified copies admissible) | - |
| Show cause notice (private land) | First proviso to s.261(1) HMC Act (reasonable opportunity); HBC 2017 Code 2.2(4) | Default 7 days (configurable per violation type) |
| Show cause notice (Corporation land) | s.408A(1) read with s.2(4A) (competent authority = Joint Commissioner) | Minimum **7 days from service** - enforced |
| Show cause notice (State Govt land) | s.4 HPP Act 1972 (Collector) - referral generated | Minimum **10 days** - enforced on the referral |
| Stop-work order | s.262(1); police requisition s.262(2); watch s.262(3)-(4) | Immediate |
| Sealing order | s.263A(1) (Act 12 of 2013); removal of seal s.263A(2); breach s.263A(3) | Appeal 7 days to Divisional Commissioner (s.263A(4)) |
| Alteration notice | s.263(1)-(3) | Period stated in the notice |
| Demolition order (private land) | s.261(1); execution s.261(6); cost as arrears of tax | Minimum **3 days** enforced; MCG default **15 days** |
| Order on Corporation land | s.408A(2); eviction/demolition s.408A(3); immediate action s.408A(4) | **Further 7 days** enforced; appeal 7 days to Commissioner (s.408B), disposal in 60 days |
| Unfit building | ss.282-284 | 30 days to vacate + 6 weeks to demolish (s.284(3)) |
| Dangerous building | s.265(2)-(6), s.315 | Period in order; immediate action if danger imminent (s.265(4)) |
| Misuse / change of use | s.265(1)(b); HBC Code 4.12 (revocation of OC) | 7 days default |
| Occupation without OC | s.264(2); HBC Code 4.10(2); vacate order s.266 | 7 days default |
| Prosecution | s.380 + Third Schedule; s.381; s.386 (complaint by Commissioner); compounding s.387 | - |
| Service of notices | s.408A(1) (post / person / affixation / beat of drum); s.402 (no invalidity for defect of form) | Geotagged proof of affixation mandatory in the app |
| Delegation to Joint Commissioner | s.401(2) | Delegation order number printed on every notice |

## 3. Violation catalogue (36 types)


### Construction / encroachment on Government or Corporation land / सरकारी / निगम भूमि पर निर्माण / अतिक्रमण

| Code | Violation | Legal basis | Action path | SCN days | Order days (min) | Compoundable | Third Sch. fine |
|---|---|---|---|---|---|---|---|
| GL-01 | Unauthorised construction / occupation on land vested in the Municipal Corporation<br>*नगर निगम में निहित भूमि पर अनधिकृत निर्माण / कब्ज़ा* | HMCA1994 s.408, HMCA1994 s.408A(1), HMCA1994 s.408A(2), HMCA1994 s.408A(3), HMCA1994 s.408A(4), HMCA1994 s.254(2)(e), HMCA1994 s.250 | HMCA_408A | 7 | 7 (7) | NO | Rs 500 |
| GL-02 | Encroachment / unauthorised construction on State Government land or other public premises<br>*राज्य सरकार की भूमि / अन्य सार्वजनिक परिसर पर अतिक्रमण / अनधिकृत निर्माण* | HPPA1972 s.3, HPPA1972 s.4, HPPA1972 s.5, HPPA1972 s.7(2)-(3), HMCA1994 s.254(2)(e), HMCA1994 s.250, HMCA1994 s.261(1), HMCA1994 s.262(1) | HPPA_4_5 | 10 | 15 (10) | NO | Rs 5,000 + Rs 500/day |
| GL-06 | Construction on or over a municipal drain, nallah, water body, pond or johad<br>*नगरपालिका नाले, नाली, जलाशय, तालाब या जोहड़ पर / के ऊपर निर्माण* | HMCA1994 s.235(1), HMCA1994 s.238(1), HMCA1994 s.408, HMCA1994 s.408A(1), HMCA1994 s.261(1) | HMCA_408A | 7 | 7 (7) | NO | Rs 1,000 + Rs 100/day |
| GL-07 | Construction on land reserved for public purpose in a sanctioned scheme / layout (park, green belt, community site, road)<br>*स्वीकृत योजना / लेआउट में सार्वजनिक प्रयोजन हेतु आरक्षित भूमि (पार्क, ग्रीन बेल्ट, सामुदायिक स्थल, सड़क) पर निर्माण* | HMCA1994 s.254(2)(g), HMCA1994 s.258(2), HMCA1994 s.267, HMCA1994 s.261(1), PSRCA1963 s.7, PSRCA1963 s.12(1) | HMCA_261 | 7 | 15 (3) | NO | Rs 1,000 |

### Unauthorised construction on private land (no sanction) / निजी भूमि पर अनधिकृत निर्माण (बिना स्वीकृति)

| Code | Violation | Legal basis | Action path | SCN days | Order days (min) | Compoundable | Third Sch. fine |
|---|---|---|---|---|---|---|---|
| PL-01 | Erection of building without sanction of building plan<br>*भवन योजना की स्वीकृति के बिना भवन का निर्माण* | HMCA1994 s.250, HMCA1994 s.251, HMCA1994 s.261(1), HMCA1994 s.262(1), HMCA1994 s.263A(1), HBC2017 s.2.1(1), HBC2017 s.2.2(4) | HMCA_261 | 7 | 15 (3) | CONDITIONAL | Rs 5,000 + Rs 500/day |
| PL-02 | Addition / alteration / structural repair without sanction<br>*स्वीकृति के बिना जोड़ / परिवर्तन / संरचनात्मक मरम्मत* | HMCA1994 s.252, HMCA1994 s.250, HMCA1994 s.261(1), HMCA1994 s.263, HBC2017 s.4.6 | HMCA_261 | 7 | 15 (3) | CONDITIONAL | Rs 500 + Rs 50/day |
| PL-03 | Construction continued after expiry / lapse of sanction validity<br>*स्वीकृति की वैधता समाप्त होने के बाद निर्माण जारी रखना* | HMCA1994 s.259, HMCA1994 s.255(3), HBC2017 s.4.3-4.4, HMCA1994 s.261(1) | HMCA_261 | 7 | 15 (3) | YES | Rs 2,000 + Rs 200/day |
| PL-04 | Sanction obtained by misrepresentation or fraudulent documents<br>*गलत बयानी या कूटरचित दस्तावेज़ों से प्राप्त स्वीकृति* | HMCA1994 s.256, HBC2017 s.4.7, HMCA1994 s.261(1) | HMCA_261 | 7 | 15 (3) | NO | Rs 5,000 + Rs 500/day |
| PL-06 | Illegal colony / unauthorised plotting or layout / roads laid without sanction<br>*अवैध कॉलोनी / अनधिकृत प्लॉटिंग या लेआउट / बिना स्वीकृति सड़कें बनाना* | HMCA1994 s.230, HMCA1994 s.231, HMCA1994 s.232, HMCA1994 s.254(2)(d), HMCA1994 s.261(1), PSRCA1963 s.7, PSRCA1963 s.12(1) | HMCA_261 | 7 | 15 (3) | NO | Rs 1,000 |
| PL-07 | Construction in controlled area / scheduled-road restricted belt without CLU / permission<br>*नियंत्रित क्षेत्र / अनुसूचित सड़क प्रतिबंधित पट्टी में सी.एल.यू. / अनुमति के बिना निर्माण* | PSRCA1963 s.3, PSRCA1963 s.7, PSRCA1963 s.12(1), PSRCA1963 s.12(2)-(3), HMCA1994 s.346(1), HMCA1994 s.250 | HMCA_261 | 7 | 15 (3) | NO | Rs 5,000 + Rs 500/day |

### Deviation from sanctioned building plan / स्वीकृत भवन योजना से विचलन

| Code | Violation | Legal basis | Action path | SCN days | Order days (min) | Compoundable | Third Sch. fine |
|---|---|---|---|---|---|---|---|
| DV-01 | Construction contrary to sanctioned plan / in contravention of conditions of sanction<br>*स्वीकृत नक्शे के विपरीत / स्वीकृति की शर्तों का उल्लंघन करते हुए निर्माण* | HMCA1994 s.255(2), HMCA1994 s.261(1), HMCA1994 s.262(1), HMCA1994 s.263, HBC2017 s.4.6, HBC2017 s.2.2(4) | HMCA_263 | 7 | 15 (0) | CONDITIONAL | Rs 2,000 + Rs 200/day |
| DV-02 | Ground coverage in excess of permissible limit<br>*अनुमेय सीमा से अधिक ग्राउंड कवरेज* | HBC2017 s.6.3, HMCA1994 s.255(2), HMCA1994 s.261(1) | HMCA_261 | 7 | 15 (3) | NO | Rs 2,000 + Rs 200/day |
| DV-03 | Floor Area Ratio (FAR) / additional floor beyond permissible<br>*अनुमेय से अधिक एफ.ए.आर. / अतिरिक्त मंज़िल* | HBC2017 s.6.3, HMCA1994 s.255(2), HMCA1994 s.261(1), HMCA1994 s.263A(1) | HMCA_261 | 7 | 15 (3) | CONDITIONAL | Rs 2,000 + Rs 200/day |
| DV-04 | Violation of front / side / rear setbacks<br>*आगे / बगल / पीछे के सेटबैक का उल्लंघन* | HBC2017 s.6.3, HMCA1994 s.263, HMCA1994 s.261(1) | HMCA_263 | 7 | 15 (0) | CONDITIONAL | Rs 2,000 + Rs 200/day |
| DV-05 | Building height beyond permissible<br>*अनुमेय से अधिक भवन की ऊँचाई* | HBC2017 s.6.3, HMCA1994 s.261(1) | HMCA_261 | 7 | 15 (3) | NO | Rs 2,000 + Rs 200/day |
| DV-06 | Basement constructed without sanction / beyond permitted extent or misused<br>*स्वीकृति के बिना / अनुमत सीमा से अधिक बेसमेंट या उसका दुरुपयोग* | HBC2017 s.7.16, HMCA1994 s.250, HMCA1994 s.261(1), HMCA1994 s.265(1) | HMCA_261 | 7 | 15 (3) | NO | Rs 2,000 + Rs 200/day |
| DV-07 | Stilt parking covered / converted or parking not provided as sanctioned<br>*स्टिल्ट पार्किंग को ढकना / बदलना या स्वीकृत पार्किंग उपलब्ध न कराना* | HBC2017 s.6.3, HBC2017 s.7.1, HMCA1994 s.263, HMCA1994 s.265(1) | HMCA_263 | 7 | 15 (0) | NO | Rs 1,000 + Rs 100/day |
| DV-08 | Unauthorised sub-division of plot / more than one building unit on a plot<br>*प्लॉट का अनधिकृत उप-विभाजन / एक प्लॉट पर एक से अधिक भवन इकाई* | HBC2017 s.6.2(1)-(2), HMCA1994 s.254(2)(d), HMCA1994 s.261(1) | HMCA_261 | 7 | 15 (3) | NO | Rs 2,000 + Rs 200/day |
| DV-09 | Unauthorised amalgamation of plots<br>*प्लॉटों का अनधिकृत समामेलन* | HBC2017 s.6.2(1)-(2), HMCA1994 s.261(1) | HMCA_263 | 7 | 15 (0) | CONDITIONAL | Rs 2,000 + Rs 200/day |
| DV-10 | Violation of zoning plan / architectural control sheet<br>*ज़ोनिंग प्लान / आर्किटेक्चरल कंट्रोल शीट का उल्लंघन* | HBC2017 s.3.5, HBC2017 s.6.4, HMCA1994 s.261(1) | HMCA_263 | 7 | 15 (0) | CONDITIONAL | Rs 2,000 + Rs 200/day |
| DV-11 | Mezzanine, mumty, pergola, chajja or projection beyond permitted limits<br>*अनुमत सीमा से अधिक मेज़ेनाइन, मुमटी, पेर्गोला, छज्जा या प्रक्षेपण* | HBC2017 s.7.12, HBC2017 s.7.13, HMCA1994 s.263 | HMCA_263 | 7 | 15 (0) | YES | Rs 2,000 |

### Encroachment on streets / footpaths / सड़क / फुटपाथ पर अतिक्रमण

| Code | Violation | Legal basis | Action path | SCN days | Order days (min) | Compoundable | Third Sch. fine |
|---|---|---|---|---|---|---|---|
| GL-03 | Structure / fixture erected on public street, footpath or road land<br>*सार्वजनिक सड़क, फुटपाथ या रोड-लैंड पर संरचना / फिक्सचर का निर्माण* | HMCA1994 s.238(1), HMCA1994 s.235(1), HMCA1994 s.235(2), HMCA1994 s.240, HMCA1994 s.216 | HMCA_235_238 | 3 | 3 (0) | NO | Rs 1,000 + Rs 100/day |
| GL-04 | Construction within the regular line of a street / building line<br>*सड़क की नियमित रेखा / भवन रेखा के भीतर निर्माण* | HMCA1994 s.224, HMCA1994 s.258(2), HMCA1994 s.252(1)(e), HMCA1994 s.261(1) | HMCA_261 | 7 | 15 (3) | NO | Rs 1,000 |
| GL-05 | Projection over street without permission (balcony, canopy, sunshade, ramp, steps)<br>*बिना अनुमति सड़क पर प्रक्षेपण (बालकनी, कैनोपी, छज्जा, रैम्प, सीढ़ियाँ)* | HMCA1994 s.235(1), HMCA1994 s.236, HMCA1994 s.235(2), HBC2017 s.7.12 | HMCA_235_238 | 7 | 7 (0) | CONDITIONAL | Rs 500 + Rs 50/day |
| GL-08 | Deposit of building material / malba on street or public land without permission<br>*बिना अनुमति सड़क या सार्वजनिक भूमि पर निर्माण सामग्री / मलबा जमा करना* | HMCA1994 s.243(1), HMCA1994 s.243(3), HMCA1994 s.238(2), HMCA1994 s.244 | HMCA_235_238 | 1 | 1 (0) | YES | Rs 500 + Rs 50/day |

### Misuse / change of use / occupation without OC / दुरुपयोग / उपयोग परिवर्तन / ओ.सी. के बिना अधिभोग

| Code | Violation | Legal basis | Action path | SCN days | Order days (min) | Compoundable | Third Sch. fine |
|---|---|---|---|---|---|---|---|
| MU-01 | Change of use of land or building without permission (e.g., residential to commercial, PG, guest house, godown)<br>*बिना अनुमति भूमि या भवन के उपयोग में परिवर्तन (जैसे आवासीय से व्यावसायिक, पी.जी., गेस्ट हाउस, गोदाम)* | HMCA1994 s.265(1), HBC2017 s.4.12, HBC2017 s.6.1, HMCA1994 s.263A(1) | HMCA_265_1 | 7 | 15 (0) | CONDITIONAL | Rs 1,000 + Rs 100/day |
| MU-02 | Occupation / use of building without completion / occupation certificate<br>*पूर्णता / अधिभोग प्रमाण-पत्र के बिना भवन का अधिभोग / उपयोग* | HMCA1994 s.264, HBC2017 s.4.10(2), HMCA1994 s.266 | HMCA_266 | 7 | 15 (0) | YES | Rs 500 + Rs 50/day |
| MU-03 | Use of inflammable materials for roof / shed / pandal without permission<br>*बिना अनुमति छत / शेड / पंडाल में ज्वलनशील सामग्री का उपयोग* | HMCA1994 s.260 | HMCA_235_238 | 3 | 3 (0) | YES | Rs 1,000 |

### Dangerous / unfit buildings / खतरनाक / अनुपयुक्त भवन

| Code | Violation | Legal basis | Action path | SCN days | Order days (min) | Compoundable | Third Sch. fine |
|---|---|---|---|---|---|---|---|
| DB-01 | Dangerous / ruinous structure likely to fall<br>*खतरनाक / जर्जर संरचना जिसके गिरने की संभावना है* | HMCA1994 s.265(2)-(6), HMCA1994 s.315, HMCA1994 s.266 | HMCA_265_2 | 3 | 7 (0) | NO | Rs 2,000 + Rs 200/day |
| DB-02 | Building unfit for human habitation<br>*मानव निवास के लिए अनुपयुक्त भवन* | HMCA1994 s.284, HMCA1994 s.282 | HMCA_284 | 30 | 42 (30) | NO | Rs 2,000 + Rs 200/day |

### Non-compliance with notices and orders / नोटिस और आदेशों का पालन न करना

| Code | Violation | Legal basis | Action path | SCN days | Order days (min) | Compoundable | Third Sch. fine |
|---|---|---|---|---|---|---|---|
| PL-05 | Commencement of work without notice of commencement / DPC certificate<br>*प्रारंभ की सूचना / डी.पी.सी. प्रमाण-पत्र के बिना कार्य प्रारंभ* | HMCA1994 s.255(4), HBC2017 s.4.9 | HMCA_263 | 7 | 7 (0) | YES | Rs 2,000 + Rs 200/day |
| PN-01 | Continuing construction after stop-work order<br>*कार्य-रोक आदेश के बाद निर्माण जारी रखना* | HMCA1994 s.262(2), HMCA1994 s.262(3), HMCA1994 s.262(4), HMCA1994 s.380, BNS2023 s.223 | HMCA_261 | 0 | 3 (3) | NO | Rs 2,000 + Rs 200/day |
| PN-02 | Failure to comply with demolition order / alteration notice<br>*ध्वस्तीकरण आदेश / परिवर्तन नोटिस का पालन न करना* | HMCA1994 s.261(6), HMCA1994 s.263, HMCA1994 s.408A(3), HMCA1994 s.380 | HMCA_261 | 0 | 0 (3) | NO | Rs 2,000 + Rs 200/day |
| PN-03 | Breaking / removal of seal<br>*सील तोड़ना / हटाना* | HMCA1994 s.263A(3), HMCA1994 s.380, BNS2023 s.223 | HMCA_261 | 0 | 3 (3) | NO | Rs 2,000 + Rs 200/day |
| PN-04 | Removal / defacing of notice affixed on premises<br>*परिसर पर चस्पा नोटिस को हटाना / विरूपित करना* | HMCA1994 s.407, HMCA1994 s.380 | HMCA_261 | 0 | 0 (3) | YES | Rs 500 |
| PN-05 | Obstruction of Corporation officials during inspection / enforcement<br>*निरीक्षण / प्रवर्तन के दौरान निगम अधिकारियों को बाधा पहुँचाना* | HMCA1994 s.405, HMCA1994 s.380, BNS2023 s.221 | HMCA_261 | 0 | 0 (3) | NO | Rs 500 |

## 4. Notice and order types generated by the system

| Code | Document | Provision | Kind | Min days | Default days | Appeal |
|---|---|---|---|---|---|---|
| SCN_261 | Show Cause Notice under section 261(1) proviso (why the unauthorised erection/work should not be demolished) | HMCA1994 s.261(1) | NOTICE | 0 | 7 | - |
| SCN_408A | Show Cause Notice under section 408A(1) (unauthorised occupation of Corporation land) | HMCA1994 s.408A(1) | NOTICE | 7 | 7 | - |
| SCN_284 | Show Cause Notice under section 284(1) (building unfit for human habitation) | HMCA1994 s.284 | NOTICE | 0 | 30 | - |
| SCN_256_CANCELLATION | Show Cause Notice under section 256 (cancellation of sanction obtained by misrepresentation) | HMCA1994 s.256 | NOTICE | 0 | 7 | - |
| ALTERATION_NOTICE_263 | Notice under section 263(1) requiring alteration of work / show cause | HMCA1994 s.263 | NOTICE | 0 | 7 | - |
| REMOVAL_NOTICE_235 | Notice under section 235(2) to remove projection / structure from street | HMCA1994 s.235(2) | NOTICE | 0 | 3 | - |
| MISUSE_NOTICE_265 | Notice under section 265(1) to discontinue unauthorised use / change of use | HMCA1994 s.265(1) | NOTICE | 0 | 7 | - |
| OC_NOTICE_264 | Notice under section 264(2) - occupation without completion / occupation certificate | HMCA1994 s.264 | NOTICE | 0 | 7 | - |
| STOP_WORK_262 | Stop-Work Order under section 262(1) | HMCA1994 s.262(1) | ORDER | 0 | 0 | - |
| SEALING_263A | Sealing Order under section 263A(1) | HMCA1994 s.263A(1) | ORDER | 0 | 0 | Divisional Commissioner, Gurugram (7 days) |
| RESEALING_263A | Re-sealing memo under section 263A | HMCA1994 s.263A(3) | ORDER | 0 | 0 | - |
| DEMOLITION_ORDER_261 | Demolition Order under section 261(1) | HMCA1994 s.261(1) | ORDER | 3 | 15 | Divisional Commissioner, Gurugram (within the period specified in this order) |
| EVICTION_DEMOLITION_ORDER_408A | Order under section 408A(2) to vacate / demolish / restore Corporation land | HMCA1994 s.408A(2) | ORDER | 7 | 7 | Commissioner, Municipal Corporation Gurugram (7 days) |
| DEMOLITION_ORDER_284 | Demolition Order under section 284(3) (unfit building) | HMCA1994 s.284 | ORDER | 30 | 30 | - |
| DANGEROUS_BUILDING_ORDER_265 | Order under section 265(2) to demolish / secure / repair dangerous building | HMCA1994 s.265(2)-(6) | ORDER | 0 | 7 | - |
| VACATE_ORDER_266 | Order under section 266(1) to vacate building | HMCA1994 s.266 | ORDER | 0 | 7 | - |
| IMMEDIATE_ACTION_265_4 | Memo of immediate action under section 265(4) (imminent danger) | HMCA1994 s.265(2)-(6) | MEMO | 0 | 0 | - |
| SUMMARY_REMOVAL_240 | Summary removal memo under section 240 / 243(3) | HMCA1994 s.240 | MEMO | 0 | 0 | - |
| POLICE_REQUISITION_262_2 | Requisition to Police under section 262(2) | HMCA1994 s.262(2) | MEMO | 0 | 0 | - |
| WATCH_DEPUTATION_262_3 | Order deputing watch under section 262(3) | HMCA1994 s.262(3) | MEMO | 0 | 0 | - |
| OC_REVOCATION_HBC_4_12 | Order revoking Occupation Certificate (HBC 2017 Code 4.12) | HBC2017 s.4.12 | ORDER | 0 | 0 | - |
| REFERRAL_TO_COLLECTOR_HPPA | Referral to the Collector for eviction under sections 4-5 of the HPP Act, 1972 | HPPA1972 s.4 | REFERRAL | 0 | 0 | - |
| REFERRAL_TO_DTCP | Referral to District Town Planner (Enforcement) under the 1963 Act | PSRCA1963 s.12(2)-(3) | REFERRAL | 0 | 0 | - |
| EXECUTION_BY_CORPORATION | Execution memo - demolition / sealing carried out by the Corporation (s.261(6) / 408A(3) / 263A(2)(c)) | HMCA1994 s.261(6) | MEMO | 0 | 0 | - |
| COST_RECOVERY | Demand for recovery of demolition cost as arrears of tax / land revenue | HMCA1994 s.261(6) | MEMO | 0 | 30 | - |
| PROSECUTION_380 | Complaint for prosecution under section 380 / 386 | HMCA1994 s.380 | MEMO | 0 | 0 | - |
| POLICE_COMPLAINT | Complaint to Police (BNS 2023 / obstruction / seal breach) | BNS2023 s.223 | MEMO | 0 | 0 | - |
| RE_AFFIXATION | Re-affixation memo (s.407) | HMCA1994 s.407 | MEMO | 0 | 0 | - |

## 5. Statutory text


### Haryana Municipal Corporation Act, 1994

**Section 2(2) - Definition - 'building'**

"building" means a shop, house, out-house, stable, latrine, urinal, shed, hut, well or any other structure whether of masonry, bricks, wood, mud, metal or other material and includes a well but does not include any portable shelter;

**Section 2(4A) - Definition - 'competent authority'**

"competent authority" means the Joint Commissioner of Corporation.

> Note: Inserted by amendment; makes the Joint Commissioner the competent authority for eviction/demolition on Corporation land under s.408A.

**Section 2(22) - Definition - 'land'**

"land" includes benefits that arise out of land, things attached to the earth or permanently fastened to anything attached to the earth and rights created by law over any street;

**Section 2(33) - Definition - 'occupier'**

"occupier" includes- (a) any person who for the time being is paying or is liable to pay to the owner the rent or any portion of the rent of the land or building in respect of which such rent is paid or is payable; (b) an owner in occupation of, or otherwise using his land or building; (c) a rent-free tenant of any land or building; (d) a licensee in occupation of any land or building; and (e) any person who is liable to pay to the owner damage for the use and occupation of any land or building;

**Section 2(36) - Definition - 'owner'** *(verify against Gazette)*

"owner", (a) when used with reference to any building and land, includes - (i) the person who receives the rent thereof or who would be entitled to receive the rent thereof if the same were let; (ii) an agent or trustee who receives such rent on account of the owner; (iii) an agent or trustee who receives the rent of or is entrusted with or concerned for, any premises devoted to religious or charitable purposes; (iv) a receiver, or manager, appointed by any court of competent jurisdiction to have the charge of, or to exercise the rights of an owner of the said building or land; and (v) a mortgagee in possession;

**Section 2(37) - Definition - 'premises'**

"premises" means any land or building or part of a building and includes - (a) the garden, ground and out-houses, if any, appertaining to a building or part of a building; and (b) any fitting affixed to a building or part of building for the more beneficial enjoyment thereof;

**Section 224 - Setting back building to regular line of streets** *(verify against Gazette)*

Where a building is set back or set forward to the regular line of a public street, the Commissioner may require the building to be set back to the regular line of the street and no person shall erect or re-erect any portion of a building within the regular line of a public street except with the written permission of the Commissioner.

> Note: Paraphrase of ss.223-225 (regular line of streets). Use the bare act for verbatim text.

**Section 235(1) - Prohibition of projection upon streets etc.**

Except as provided in section 236, no person shall erect, set-up, add to, or place against or in front of any premises any structure or fixture which will,- (a) overhang, jut or project into, or in any way encroach upon and obstruct in any way the safe or convenient passage of the public along any street, or (b) jut or project into or encroach upon any drain or open channel in any street so as in any way to interfere with the use or proper working of such drain or channel or to impede the inspection or cleansing thereof.

**Section 235(2) - Notice to remove projection**

The Commissioner may by notice require the owner or occupier of any premises to remove or to take such other action as he may direct in relation to any structure or fixture which has been erected, set-up, added to or placed against, or in front of, the said premises in contravention of this section.

**Section 236 - Projections over streets may be permitted in certain cases**

(1) The Commissioner may give a written permission, on such terms and on payment of such fee as he in each case thinks fit, to the owner or occupier of the building or any street,- (a) to erect an arcade over such street or any portion thereof; or (b) to put up a verandah, balcony, arch, connecting passage, sunshade, weather frame, canopy, awning or other such structure or thing projecting from any storey over or across any street or portion thereof: Provided that no permission shall be given by the Commissioner for the erection of an arcade in any public street in which construction of an arcade has not been generally sanctioned by the Corporation. (2) The Commissioner may at any time by notice require the owner or occupier of any building to remove a verandah, balcony, sunshade, weather frame or the like put up in accordance with the provisions of this Act and such owner or occupier shall be bound to take action accordingly but shall be entitled to compensation for the loss caused to him by such removal and the cost incurred thereon.

> Third Schedule: Rs 500 + Rs 50/day

**Section 238(1) - Prohibition of structures, fixtures or deposit of things in streets**

No person shall, except with the permission of the Commissioner granted in this behalf, erect or set-up any wall, fence, rail, post, step, booth or other structure whether fixed or movable or whether of a permanent or temporary nature, or any fixture in or upon any street or upon or over any open channel, drain, well or tank in any street so as to form an obstruction to or an encroachment upon, or projection over, or to occupy any portion of such street, channel, drain, well or tank.

> Third Schedule: Rs 1,000 + Rs 100/day

**Section 238(2) - Deposit of things in streets**

No person shall, except with the permission of the Commissioner and on payment of such fee as he in each case thinks fit, place or deposit upon any street, or upon any open channel, drain or well in any street or upon any public place any stall, chair, bench, box, ladder, bale or other thing whatsoever so as to form an obstruction thereto or encroachment thereon.

> Third Schedule: Rs 500

**Section 240 - Power to remove anything deposited or exposed for sale in contravention of this Act**

The Commissioner may, without notice, cause to be removed- (a) any stall, chair, bench, box, ladder, bale or other thing whatsoever placed, deposited, projected, attached or suspended in, upon, from or to any place in contravention of this Act; (b) any article whatsoever hawked or exposed for sale on any public place in contravention of this Act and any vehicle, package, box or any other thing in or on which such article is placed.

**Section 243(1) - Streets not to be opened or broken up and building materials not to be deposited therein without permission**

No person other than the Commissioner or a Corporation Officer or other Corporation employee shall, without the written permission of the Commissioner- (a) open, break up, displace, take up or make any alteration in, or cause any injury to the soil or pavement or any wall, fence, post, chain or other material or thing forming part of any street; or (b) deposit any building material in any street; or (c) set up in any street any scaffold or any temporary erection for the purpose of any work whatever, or any posts, bars, rails, boards or other things by way of an enclosure, for the purpose of making mortar or depositing bricks, lime, rubbish or other materials.

> Third Schedule: Rs 500 + Rs 50/day

**Section 243(3) - Removal of material deposited without permission**

The Commissioner may, without notice, cause to be removed any of the things referred to in clause (b) or clause (c) of sub-section (1) which has been deposited or set up in any street without the permission specified in that sub-section or which having been deposited or set up with permission has not been removed within the period specified in the notice issued under sub-section (2).

**Section 244 - Disposal of things removed under this Chapter**

(1) Any of the things caused to be removed by the Commissioner under this Chapter shall, unless the owner thereof turns up to take back such things and pays to the Commissioner the charges for the removal and storage of such things, be disposed of by public auction or in such other manner and within such time as the Commissioner thinks fit. (2) The charges for removal and storage of the things sold under sub-section (1) shall be paid out of the proceeds of the sale thereof and the balance, if any, shall be paid to the owner of the things sold on a claim being made therefor within a period of two years from the date of sale, and if no such claim is made within the said period, shall be credited to the Corporation.

**Section 246(1) - Commissioner to take steps for repairing or enclosing dangerous places**

If any place is, in the opinion of the Commissioner, for want of sufficient repair or protection or enclosure, or owing to some work being carried on thereupon, dangerous or causing inconvenience to passengers along a street or to other persons including the owner or occupier of the said place, who have legal access thereto or to the neighbourhood thereof, the Commissioner may by notice in writing require the owner or occupier of such place to repair, protect or enclose the same or take such other steps as shall appear to the Commissioner necessary in order to prevent the danger or inconvenience arising therefrom.

> Third Schedule: Rs 500 + Rs 50/day

**Section 250 - Prohibition of erection of building without sanction**

No person shall erect or commence to erect any building or execute any of the works specified in section 252 except with the previous sanction of the Commissioner, nor otherwise than in accordance with the provisions of this Chapter and of the bye-laws made under this Act in relation to the erection of buildings or execution of works.

> Third Schedule: Rs 5,000 + Rs 500/day

**Section 251 - Erection of building - notice for sanction**

(1) Every person who intends to erect a building shall apply for sanction by giving notice in writing of his intention to the Commissioner in such form and containing such information as may be prescribed by bye-laws made in this behalf. (2) Every such notice shall be accompanied by such documents and plans as may be prescribed.

> Third Schedule: Rs 500

**Section 252 - Application for addition to, or repairs of building**

(1) Every person who intends to execute any of the following works, namely:- (a) to make any addition to a building; (b) to make any alteration or repairs to a building involving the removal or re-erection of any external or partition wall thereof or of any wall which supports the roof thereof to an extent exceeding one half of such wall above the plinth level, such half to be measured in superficial metres; (c) to make any alteration or repairs to a frame building involving the removal or re-erection of more than one half of the posts in any wall which support the roof thereof to an extent exceeding one half of such wall above the plinth level, such half to be measured in superficial metres; (d) to make any alteration in a building involving- (i) the sub-division of any room in such building so as to convert the same into two or more separate rooms; or (ii) the conversion of any passage or space in such building into a room or rooms; (e) to repair, remove, construct, reconstruct, or make any addition to or structural alteration in any portion of a building abutting on a street which stands within the regular line of such street; (f) to close permanently any door or window in an external wall; (g) to remove or reconstruct the principal staircase or to alter its position, shall apply for sanction by giving notice in writing of his intention to the Commissioner in such form and containing such information as may be prescribed by bye-laws made in this behalf. (2) Every such notice shall be accompanied by such documents and plans as may be so prescribed.

> Third Schedule: Rs 500 + Rs 50/day

**Section 253 - Conditions of valid notice**

(1) A person giving the notice required by section 251 shall specify the purpose for which it is intended to use the building to which such notice relates, and a person giving the notice required by section 252 shall specify whether the purpose for which the building is being used is proposed or likely to be changed by the execution of the proposed work. (2) No notice shall be valid until the information required under sub-section (1) and any further information and plans which may be required by bye-laws made in this behalf have been furnished to the satisfaction of the Commissioner along with the notice.

**Section 254 - Sanction or refusal of building or works**

(1) The Commissioner shall sanction the erection of a building or the execution of a work, unless such building or work would contravene any of the provisions of sub-section (2) of this section or of the provisions of section 258. (2) The grounds on which the sanction of a building or work may be refused shall be the following, namely:- (a) that the building or work, or the use of the site for the building or work or any of the particulars comprised in the site plan, ground plan, elevation section or specification would contravene the provisions of any bye-laws made in this behalf or of any other law or of any rule, bye-law or order made under such other law; (b) that the notice for sanction does not contain the particulars or is not prepared in the manner required under the bye-laws made in this behalf; (c) that any information or documents required by the Commissioner under this Act or any bye-laws made thereunder has or have not been duly furnished; (d) that in cases falling under section 230, lay out plans have not been sanctioned in accordance with section 231; (e) that the building or work would be an encroachment on Government land or land vested in the Corporation; (f) that the site of the building or work does not abut on a street or projected street and that there is no access to such building or work from any such street by a passage or pathway appertaining to such site; (g) that the building or work would be in contravention of any scheme sanctioned under section 267; (h) that the building for habitation does not provide for a flush or a water seal latrine. (3) The Commissioner shall communicate the sanction to the person who has given the notice, and where he refuses sanction on any of the grounds specified in sub-section (2) of this section or under section 258 he shall record a brief statement of his reasons for such refusal and communicate the refusal along with the reasons therefor to the person who has given the notice. (4) The sanction or refusal as aforesaid shall be communicated in such manner as may be specified in the bye-laws made in this behalf.

**Section 255 - When building or work may be proceeded with**

(1) Where within a period of sixty days after the receipt of any notice under section 251 or section 252 or of the further information, if any, required under section 253 the Commissioner does not refuse to sanction the building or work or upon refusal does not communicate the refusal to the person who has given the notice, the Commissioner shall be deemed to have accorded sanction to the building or work and the person by whom the notice has been given shall be free to commence and proceed with the building or work in accordance with his intention as expressed in the notice and the documents and plans accompanying the same: Provided that if it appears to the Commissioner that the site of the proposed building or work is likely to be affected by any scheme of acquisition of land for any public purpose or by any proposed regular line of a public street or extension, improvement, widening or alteration of any street, the Commissioner may withhold sanction of the building or work for such period not exceeding three months as he deems fit and the period of sixty days shall be deemed to commence from the date of the expiry of the period for which the sanction has been withheld. (2) Where a building or work is sanctioned or is deemed to have been sanctioned by the Commissioner under sub-section (1), the person who has given the notice shall be bound to erect the building or execute the work in accordance with such sanction but not so as to contravene any of the provisions of this Act or any other law or of any bye-law made thereunder. (3) If the person or any one lawfully claiming under him does not commence the erection of the building or the execution of the work within one year of the date on which the building or work is sanctioned or is deemed to have been sanctioned, he shall have to give notice under section 252 or, as the case may be, under section 251 for fresh sanction of the building or the work and the provisions of this section shall apply in relation to such notice as they apply in relation to the original notice. (4) Before commencing the erection of a building or execution of a work within the period specified in sub-section (3), the person concerned shall give notice to the Commissioner of the proposed date of the commencement of the erection of the building or the execution of the work: Provided that if the commencement does not take place within seven days of the date so notified the notice shall be deemed not to have been given and a fresh notice shall be necessary in this behalf.

> Note: Third Schedule fine shown is for s.255(4) (commencement of work without notice).

> Third Schedule: Rs 2,000 + Rs 200/day

**Section 256 - Sanction accorded under misrepresentation**

If at any time after the sanction of any building or work has been accorded, the Commissioner is satisfied that such sanction was accorded in consequence of any material misrepresentation or fraudulent statement contained in the notice given or information furnished under sections 251, 252 and 253 he may by order in writing, cancel for reasons to be recorded such sanction and any building or work commenced, erected, or done shall be deemed to have been commenced, erected or done without such sanction: Provided that before making any such order the Commissioner shall give reasonable opportunity to the person affected as to why such order should not be made.

**Section 258(2) - Buildings within regular line of street or in contravention of scheme**

The erection of any such building or the execution of any such work may be refused by the Commissioner if such building or any portion thereof or such work comes within the regular line of any street, the position and direction of which has been laid down by the Commissioner but which has not been actually constructed or if such building or any portion thereof or such work is in contravention of any building or any other scheme or plan prepared under this Act, or any other law for the time being in force.

> Third Schedule: Rs 1,000

**Section 259 - Period for completion of building or work**

The Commissioner when sanctioning the erection of a building or execution of a work, shall specify a reasonable period after the commencement of the building or work within which the building or work is to be completed and if the building or work is not completed within the period so specified it shall not be continued thereafter without fresh sanction obtained in the manner hereinbefore provided, unless the Commissioner on application made therefor, has allowed an extension of that period.

**Section 260 - Prohibition against use of inflammable materials for buildings etc. without permission**

In such areas as may be specified by bye-laws made in this behalf, no roof, verandah, pandal or wall of a building or no shed or fence shall be constructed or reconstructed of cloth, grass, leaves, mats or other inflammable material except with the written permission of the Commissioner nor shall any such roof, verandah, pandal, wall, shed, fence constructed or reconstructed in any year be retained in a subsequent year except with fresh permission obtained in this behalf.

> Third Schedule: Rs 1,000

**Section 261(1) - Order of demolition and stoppage of building and works in certain cases - show cause and demolition order**

Where the erection of any work has been commenced, or is being carried on or has been completed without or contrary to the sanction referred to in section 254 or in contravention of any condition subject to which such sanction has been accorded or in contravention of any of the provisions of this Act, or bye-laws made thereunder, the Commissioner may in addition to any other action that may be taken under this Act, make an order directing that such erection or work shall be demolished by the person at whose instance the erection or work has been commenced or is being carried on or has been completed within such period (not being less than three days from the date on which copy of the order of demolition with a brief statement of the reasons therefor has been delivered to that person) as may be specified in the order of demolition: Provided that no order of demolition shall be made unless the person has been given by means of a notice served in such manner as the Commissioner may think fit, a reasonable opportunity of showing cause why such order should not be made: Provided further that where the erection or work has not been completed the Commissioner may by the same order or by a separate order, whether made at the time of the issue of the notice under the first proviso or at any other time, direct the person to stop the erection or work until the expiry of the period within which an appeal against the order of demolition, if made, may be preferred under sub-section (2).

> Third Schedule: Rs 2,000 + Rs 200/day

**Section 261(2) - Appeal against demolition order** *(verify against Gazette)*

Any person aggrieved by an order of the Commissioner made under sub-section (1) may prefer an appeal against the order to the Divisional Commissioner within the period specified in the order for the demolition of the erection or work to which it relates.

> Note: Words 'court of the District Judge' substituted by 'Divisional Commissioner' by Haryana Act 1 of 2007 (w.e.f. 14.02.2007). The latestlaws PDF still shows 'District Judge' in sub-section (2) but 'Divisional Commissioner' in (3)-(6); the appellate authority is the Divisional Commissioner.

**Section 261(3) - Stay of demolition order on appeal**

Where an appeal is preferred under sub-section (2) against an order of demolition the Divisional Commissioner may stay the enforcement of that order on such terms, if any, and for such period, as it may think fit: Provided that where the erection of any building or execution of any work has not been completed at the time of the making of the order of demolition, no order staying the enforcement of the order of demolition shall be made by the Divisional Commissioner unless security, sufficient in the opinion of the Divisional Commissioner, has been given by the appellant for not proceeding with such erection or work pending the disposal of the appeal.

**Section 261(4) - Bar of suits / injunctions**

Save as provided in this section no court shall entertain any suit, application or other proceeding for injunction or other relief against the Commissioner or restrain him from taking any action or making any order in pursuance of the provisions of this section.

**Section 261(5) - Finality of order**

Every order made by the Divisional Commissioner on appeal and subject only to such order, the order of demolition made by the Commissioner shall be final and conclusive.

**Section 261(6) - Execution of demolition order by the Commissioner and recovery of cost**

Where no appeal has been preferred against an order of demolition made by the Commissioner under sub-section (1) or where an order of demolition made by the Commissioner under that sub-section has been confirmed on appeal, whether with or without variation, the person against whom the order has been made shall comply with the order within the period specified therein or, as the case may be, within the period, if any, fixed by the Divisional Commissioner on appeal, and on the failure of the person to comply with the order within such period, the Commissioner may himself cause the erection or the work to which the order relates to be demolished and the expenses of such demolition shall be recoverable from such person as an arrear of tax under this Act.

**Section 262(1) - Order of stoppage of building or works in certain cases (stop-work order)**

Where the erection of any building or execution of any work has been commenced or is being carried on (but has not been completed) without or contrary to the sanction referred to in section 254 or in contravention of any condition subject to which such sanction has been accorded or in contravention of any provisions of this Act or bye-laws made thereunder, the Commissioner may in addition to any other action that may be taken under this Act by order, require the person at whose instance the building or the work has been commenced or is being carried on, to stop the same forthwith.

> Third Schedule: Rs 2,000 + Rs 200/day

**Section 262(2) - Police assistance to enforce stop-work order**

If an order made by the Commissioner under section 261 or under sub-section (1) of this section directing any person to stop the erection of any building or execution of any work is not complied with, the Commissioner may require any police officer to remove such person and all his assistants and workmen from the premises within such time as may be specified in the requisition and such police officer shall comply with the requisition accordingly.

**Section 262(3) - Deputation of watch on premises**

After the requisition under sub-section (2) has been complied with, the Commissioner may, if he thinks fit, depute by a written order a police officer or a Corporation officer or other Corporation employee to watch the premises in order to ensure that the erection of the building or the execution of the work is not continued.

**Section 262(4) - Cost of watch recoverable**

Where a police officer or a Corporation Officer or other Corporation employee has been deputed under sub-section (3) to watch the premises, the cost of such deputation shall be paid by the person at whose instance such erection or execution is being continued or to whom notice under sub-section (1) was given and shall be recoverable from such person as an arrear of tax under this Act.

**Section 263 - Power of Commissioner to require alteration of work**

(1) The Commissioner may, at any time during the erection of any building or execution of any work or at any time within three months after the completion thereof, by a written notice specify any matter in respect of which such erection or execution is without or contrary to the sanction referred to in section 254 or is in contravention of any condition of such sanction or any of the provisions of this Act or any bye-laws made thereunder and require the person who gave the notice under section 251 or section 252 or the owner of such building or work either- (a) to make such alterations as may be specified in the said notice with the object of bringing the building or work in conformity with the said sanction, condition or provisions; or (b) to show cause why such alterations should not be made within the period stated in the notice. (2) If the person or the owner does not show cause as aforesaid, he shall be bound to make the alterations specified in the notice. (3) If the person or the owner shows cause as aforesaid, the Commissioner shall by an order either cancel the notice issued under sub-section (1) or confirm the same subject to such modifications as he thinks fit.

> Third Schedule: Rs 2,000

**Section 263A(1) - Power to seal premises**

The Commissioner may, at any time, before or after making an order under section 261 or 262 may order to seal the premises.

> Note: Inserted by Haryana Act 12 of 2013 (Haryana Govt. Gazette (Extra.) 26.09.2013).

**Section 263A(2) - Removal of seal - purposes**

Where any premises has been sealed, the Commissioner may order such seal to be removed for the purpose of- (a) allowing an opportunity to the owner to bring it in conformity with the sanctioned building plan as per the provisions of this Act, rules or bye-laws framed thereunder within a period, which shall not exceed three months; or (b) allowing the functionaries of the Corporation to bring it in conformity with the sanctioned building plan as per the provisions of this Act, rules or bye-laws framed thereunder at the cost of the owner; or (c) demolition, at the cost of the owner.

**Section 263A(3) - Prohibition on removal of seal**

No person shall remove such seal except- (a) under an order made by the Commissioner under sub-section (2); or (b) under an order of the appellate authority.

**Section 263A(4) - Appeal against sealing order**

Where any order of sealing has been passed under sub-section (1), the owner may file an appeal before the Divisional Commissioner concerned within a period of seven days of passing of such order. The Divisional Commissioner may either reject the appeal or stay the order to allow the owner to bring the premises in accordance with the sanctioned building plan as per the provisions of this Act, rules or the bye-laws framed thereunder, with such conditions including furnishing of a bank guarantee of an amount, as deemed fit. On failure of the owner to adhere to the conditions of the order, bank guarantee shall be revoked and the premises shall be liable for demolition, at the cost of the owner. Such cost shall be paid by the owner within a period of one month from the date of demolition of the said premises.

**Section 263A(5) - Recovery of demolition cost as arrears of land revenue** *(verify against Gazette)*

In the event of non-payment of the cost by the owner as per sub-section (4), the same shall be recoverable as arrears of land revenue.

> Note: Gazette text reads 'as per sub-section (3)'; the cross-reference appears to be to sub-section (4).

**Section 264 - Completion certificate and prohibition on occupation**

(1) Every person who employs a licensed architect or engineer or a person approved by the Commissioner to design or erect a building or execute any work shall, within one month after the completion of the erection of the building or execution of the work, deliver or send or cause to be delivered or sent to the Commissioner a notice in writing of such completion accompanied by a certificate in the form prescribed by bye-laws made in this behalf and shall give to the Commissioner all necessary facilities for the inspection of such building or work. (2) No person shall occupy or permit to be occupied any such building or use or permit to be used any building or a part thereof affected by any such work until permission has been granted by the Commissioner in this behalf in accordance with bye-laws made under this Act: Provided that if the Commissioner fails within a period of thirty days after the receipt of the notice of completion to communicate his refusal to grant such permission, it shall be deemed to have been granted.

> Third Schedule: Rs 500 + Rs 50/day

**Section 265(1) - Restrictions on use of buildings**

No person shall, without the written permission of the Commissioner, or otherwise than in conformity with the conditions, if any, of such permission- (a) use or permit to be used for human habitation any part of a building not originally erected or authorised to be used for that purpose or not used for that purpose before any alteration has been made therein by any work executed in accordance with the provisions of this Act and of the bye-laws made thereunder; (b) change or allow the change of the use of any land or building; (c) convert or allow the conversion of one kind of tenement into another kind.

> Third Schedule: Rs 1,000 + Rs 100/day

**Section 265(2)-(6) - Removal of dangerous buildings**

(2) If it appears to the Commissioner at any time that any building is in a ruinous condition, or likely to fall, or in any way dangerous to any person occupying, resorting to or passing by such building or any other building or place in the neighbourhood of such building, the Commissioner may, by order in writing, require the owner or occupier of such building to demolish, secure or repair such building or do one or more of such things within such period as may be specified in the order, as to prevent all cause of danger therefrom. (3) The Commissioner may also, if he thinks fit, require such owner or occupier by the order made under sub-section (2) either forthwith or before proceeding to demolish, secure or repair the building to set up a proper and sufficient board or fence for the protection of passers-by and other persons, with a convenient platform and hand rail wherever practicable to serve as a footway for passengers outside of such board or fence. (4) If it appears to the Commissioner that danger from a building which is in ruinous condition or likely to fall is imminent, he may, before making the order aforesaid, fence off, demolish, secure or repair the said building or take such steps as may be necessary to prevent the danger. (5) If the owner or occupier of the building does not comply with the order within the period specified therein, the Commissioner shall take such steps in relation to the building as to prevent all cause of danger therefrom. (6) All expenses incurred by the Commissioner in relation to any building under this section shall be recoverable from the owner or occupier thereof as an arrear of tax under this Act.

> Third Schedule: Rs 2,000 + Rs 200/day

**Section 266 - Power to order building to be vacated in certain circumstances**

(1) The Commissioner may by order in writing direct that any building, which in his opinion is in a dangerous condition or is not provided with sufficient means of egress in case of fire or is occupied in contravention of section 264, be vacated forthwith or within such period as may be specified in the order: Provided that at the time of making such order the Commissioner shall record a brief statement of the reasons therefor. (2) If any person fails to vacate the building in pursuance of such order the Commissioner may direct any police officer to remove such person from the building and the police officer shall comply with such direction accordingly. (3) The Commissioner shall, on the application of any person who has vacated, or has been removed from any building in pursuance of an order made by him, allow such person to reoccupy the building on the expiry of the period for which the order has been in force; provided that the reasons on account of which the vacation was ordered have been rectified or have ceased to exist.

> Third Schedule: Rs 1,000 + Rs 100/day

**Section 284 - Power of Commissioner to order demolition of buildings unfit for human habitation**

(1) Notwithstanding anything contained in section 144 of the Code of Criminal Procedure, 1973, where the Commissioner upon any information in his possession is satisfied that any building is unfit for human habitation and is not capable at a reasonable expense of being rendered so fit, he shall serve upon the owner of the building and upon any other person having an interest in the building, whether as a lessee, mortgagee or otherwise a notice to show cause within such time as may be specified in the notice as to why an order of demolition of the building should not be made. (2) If any of the persons upon whom a notice has been served under sub-section (1), appears in pursuance thereof before the Commissioner and gives an undertaking to him that such person shall, within a period specified by the Commissioner, execute such works of improvement in relation to the building as will, in the opinion of the Commissioner render the building fit for human habitation or an undertaking that the building shall not be used for human habitation until the Commissioner, on being satisfied that it has been rendered fit for that purpose, cancels the undertaking, the Commissioner shall not make an order of demolition of the building. (3) If no such undertaking as is mentioned in sub-section (2) is given, or if in a case where any such undertaking has been given, any work of improvement to which the undertaking relates is not carried out within the specified period or the building is at any time used in contravention of the terms of the undertaking, the Commissioner shall forthwith make an order of demolition of the building requiring that the building shall be vacated within a period to be specified in the order not being less than thirty days from the date of the order, and that it shall be demolished within six weeks of the expiration of that period. (4) Where an order of demolition of a building under this section has been made, the owner of building or any other person having an interest therein shall demolish that building within the time specified in that behalf by the order, and if the building is not demolished within that time, the Commissioner shall demolish the building and sell the materials thereof. (5) Any expenses incurred by the Commissioner under sub-section (4), if not satisfied out of the proceeds of the sale of materials of the building, shall be recovered from the owner of the building or any other person having an interest therein as an arrear of tax under this Act.

> Third Schedule: Rs 2,000 + Rs 200/day

**Section 315 - Power to require buildings, wells etc. to be rendered safe**

Where any building, or wall, or anything affixed thereto, or any well, tank, reservoir, pool, depression or excavation, or any bank or tree, is in the opinion of the Commissioner, in a ruinous state for want of sufficient repairs, protection or enclosure, a nuisance or dangerous to persons passing by or dwelling or working in the neighbourhood, the Commissioner may by notice in writing require the owner or part-owner or person claiming to be the owner or part-owner thereof or failing any of them, the occupier thereof, to remove the same or may require him to repair, protect or enclose the same in such manner as he thinks necessary and if the danger is, in the opinion of the Commissioner, imminent, he shall forthwith take such steps as he thinks necessary to avert the same.

**Section 346(1) - Declaration of controlled area**

Notwithstanding any law for the time being in force, the Commissioner may, with the previous approval of the Government, by notification, declare the whole or any part of the area within the Corporation to be a controlled area provided that the same has not been declared as controlled area under the Punjab Scheduled Roads and Controlled Areas Restriction of Unregulated Development Act, 1963 (Act 41 of 1963).

**Section 380 - Punishment for certain offences (Third Schedule)**

Whoever- (a) contravenes any provision of any of the sections, sub-sections, clauses, provisos or other provisions of this Act mentioned in the first column of the table in the Third Schedule; or (b) fails to comply with any order lawfully given to him or any requisition lawfully made upon him under any of the said sections, sub-sections, clauses, provisos or other provisions shall be punishable- (i) with fine which may extend to the amount specified in the third column of the said Table; and (ii) in the case of a continuing contravention or failure, with an additional fine which may extend to the amount specified in the fourth column of that Table for every day during which such contravention or failure continues after conviction for the first such contravention or failure.

**Section 381 - General penalty**

Whoever, in any case in which a penalty is not expressly provided by this Act, fails to comply with any notice, order or requisition issued under any provisions thereof, or otherwise contravenes any of the provisions of this Act, shall be punishable with fine which may extend to five hundred rupees, and in the case of a continuing failure or contravention with an additional fine which may extend to fifty rupees for every day after the first, during which he has persisted in the failure or contravention.

> Third Schedule: Rs 500 + Rs 50/day

**Section 382 - Offences by companies** *(verify against Gazette)*

(1) Where an offence under this Act has been committed by a company, every person who, at the time the offence was committed, was in charge of and was responsible to the company for the conduct of the business of the company, as well as the company, shall be deemed to be guilty of the offence and shall be liable to be proceeded against and punished accordingly: Provided that nothing contained in this sub-section shall render any such person liable to any punishment provided in this Act, if he proves that the offence was committed without his knowledge or that he exercised all due diligence to prevent the commission of such offence. (2) Notwithstanding anything contained in sub-section (1) where an offence under this Act has been committed by a company and it is proved that the offence has been committed with the consent or connivance of, or is attributable to any neglect on the part of, any director, manager, secretary or other officer of the company, such director, manager, secretary or other officer shall also be deemed to be guilty of that offence and shall be liable to be proceeded against and punished accordingly.

**Section 386 - Prosecution**

Save as otherwise provided in this Act, no court shall try an offence made punishable by or under this Act or any rule or any bye-law made thereunder, except on the complaint of, or upon information received from the Commissioner, or any other officer of the Corporation authorised by it in this behalf.

**Section 387 - Composition of offences**

(1) The Commissioner or any other officer of the Corporation authorised by it in this behalf by a general or special order or a sub-committee of the Corporation appointed by it may, either before or after the institution of the proceedings, compound any offence made punishable by or under this Act or any rule or any bye-law made thereunder. (2) Where an offence has been compounded, the offender, if in custody, shall be discharged and no further proceedings shall be taken against him in respect of the offence so compounded.

**Section 388 - Protection of action of the Corporation etc.**

No suit or prosecution shall be entertained in any court against the Corporation or against the Commissioner or against any Corporation Officer or other Corporation employee or against any person acting under the order or direction of the Corporation, the Commissioner or any Corporation officer or other Corporation employee, for anything which is in good faith done or intended to be done, under this Act or any rule, regulation or bye-law made thereunder.

**Section 393 - Penalty for breaches of bye-laws**

(1) Any bye-law made under this Act may provide that a contravention thereof shall be punishable- (a) with fine which may extend to five hundred rupees; or (b) with fine which may extend to five hundred rupees and in the case of continuing contravention, with an additional fine which may extend to fifty rupees for every day during which such contravention continues after conviction for the first contravention; or (c) with fine which may extend to fifty rupees for every day during which the contravention continues, after the receipt of a notice from the Commissioner or any Corporation officer duly authorised in that behalf by the person contravening the bye-law requiring such person to discontinue such contravention. (2) Any such bye-law may also provide that a person contravening the same shall be required to remedy so far as lies in his power, the mischief, if any, caused by such contravention.

**Section 401(2) - Delegation by the Commissioner** *(verify against Gazette)*

The Commissioner may, by order direct that any power exercisable or duty to be performed by him under this Act or any rule, regulation or bye-law made thereunder may be exercised or performed by a Corporation officer or other Corporation employee.

> Note: Basis on which the Joint Commissioner exercises the Commissioner's powers under ss.261, 262, 263 and 263A. The delegation order number must be quoted in every notice/order.

**Section 402 - Validity of notices and other documents**

No notice, order, requisition, licence, permission in writing or any other document issued under this Act, shall be invalid merely by reason of defect of form.

**Section 403 - Admissibility of document or entry as evidence**

A copy of any receipt, application, plan, notice, order or other document or of any entry in a register in the possession of any Corporation authority shall, if duly certified by the legal keeper thereof or other person authorised by the Commissioner in this behalf, be admissible in evidence of the existence of the document or entry and shall be admitted as evidence of the matters and transactions therein recorded in every case where, and to the same extent to which, the original document or entry would if produced, have been admissible to prove such matters and transactions.

> Note: Basis for treating the system's digitally signed notices, geotagged photographs and audit log as certified records.

**Section 405 - Prohibition against obstruction of Corporation authority etc.** *(verify against Gazette)*

No person shall obstruct the Corporation or the Commissioner, the Mayor or any of the Deputy Mayors, any members or any person employed by the Corporation or any person with whom the Commissioner has entered into a contract on behalf of the Corporation, in the performance of their duty or of anything which they are empowered or required to do by virtue or in consequence of any provision of this Act or of any rule, regulation or bye-law made thereunder.

> Third Schedule: Rs 500

**Section 407 - Prohibition against removal or obliteration of notice**

No person shall, without authority in that behalf remove, destroy, deface or otherwise obliterate any notice exhibited by or under orders of the Corporation or any other Corporation authority or any Corporation Officer or other Corporation employee specified by the Commissioner in this behalf.

> Third Schedule: Rs 500

**Section 408 - Prohibition against unauthorised removal, deposit, encroachment on Corporation land**

No person shall, without authority in that behalf, remove earth, sand or other material or deposit any matter or make any encroachment in or on any land vested in the Corporation or in any way obstruct the same.

> Third Schedule: Rs 500

**Section 408A(1) - Power to evict persons from Corporation premises/land - show cause notice**

If the competent authority is satisfied- (a) that any person authorised to occupy any premises of the Corporation has- (i) not paid rent lawfully due from him in respect of such premises for a period of more than two months; or (ii) sublet, without the permission of the Commissioner or any other officer duly empowered to grant such permission, the whole or any part of such premises; or (iii) otherwise acted in contravention of any of the terms expressed or implied, under which he is authorised to occupy such premises; or (b) that any person is in unauthorised occupation of any premises/land or building/structure constructed thereon, of the Corporation, the competent authority may, notwithstanding anything contained in any law for the time being in force, by notice served upon him by post or by person and if such person avoids service or is not available for service of notice or refuses to accept notice, then by affixing a copy of it on the outer door or some other conspicuous part of such premises/land or building or by beating of drums or in such manner, as may be prescribed, call upon such person to appear and show cause why he should not be ordered to vacate the said premises/land or building/structure constructed thereon or demolish unauthorised construction and to restore to its original state or to bring it in conformity with the provisions of this Act or rules framed thereunder, as the case may be, within a period of seven days from the date of service of the notice.

> Note: Inserted by amendment (footnote 30 in the bare act). 'Competent authority' = Joint Commissioner, s.2(4A).

**Section 408A(2) - Order to vacate / demolish / restore**

If such person fails to show cause to the satisfaction of the competent authority or fails to appear or refuses to appear before the competent authority, as the case may be, within a period of seven days, the competent authority shall pass an order requiring him to vacate such premises/land or building/structure constructed thereon or demolish unauthorised construction and restore to its original state or to bring it in conformity with the provisions of this Act or the rules framed thereunder, as the case may be, within a further period of seven days.

**Section 408A(3) - Eviction / demolition by the competent authority and recovery of cost**

If the order made under sub-section (2) is not carried out or complied with within the specified period, the competent authority at the expiry of the period so specified, shall evict that person from, and take possession of, the premises/land or building/structure constructed thereon or demolish unauthorised construction or restore to its original state or bring it in conformity with the provisions of this Act or the rules framed thereunder, as the case may be, and shall for that purpose use such force, as may be necessary and the cost incurred on such measures shall, if not paid on demand being made to him, be recoverable from such persons as arrears of land revenue.

**Section 408A(4) - Immediate action where contravention continues**

Even before the expiry of a further period of seven days mentioned under sub-section (2), if the competent authority is satisfied that instead of vacation of premises/land or building/structure constructed thereon or demolition of unauthorised construction, as the case may be, the person continues with the contravention, the competent authority shall himself take such measures and use such force as may appear necessary to give effect to the order under sub-section (2) and the cost of such measures shall if not paid on demand being made to him, be recoverable from such person as arrears of land revenue.

**Section 408B - Appeal against order under s.408A**

(1) Any person aggrieved by an order of the competent authority under sub-section (2) of section 408A may, within a period of seven days from the date of the order under sub-section (2) of section 408A, prefer an appeal to the Commissioner. (2) Where an appeal is preferred under sub-section (1), the Commissioner may stay the enforcement of the order of the competent authority for such period and on such conditions, as it deems fit. (3) Every appeal under this section shall be disposed of by the Commissioner within a period of sixty days.

**Section 408C - Finality of order**

Save as otherwise expressly provided in this Act, every order made by the competent authority under section 408A or by the Commissioner under section 408B shall be final and shall not be called in question in any original suit, application or execution proceedings and no injunction shall be granted by any court or other authority in respect of any action taken or to be taken in pursuance of any power conferred by or under sections 408A and 408B of this Act.

**Section Third Schedule - Table of fines referred to in section 380 (building and street provisions)**

Section 235 - projection upon streets: fine as per Schedule; Section 236(2) - failure to remove verandah/balcony: Rs 500 + Rs 50/day; Section 237: Rs 1,000 + Rs 50/day; Section 238(1) - erection of structure/fixture obstructing streets: Rs 1,000 + Rs 100/day; Section 238(2) - deposit of things in streets: Rs 500; Section 243(1) - opening streets / depositing building material without permission: Rs 500 + Rs 50/day; Section 246(1): Rs 500 + Rs 50/day; Section 250 - erection of building without sanction of the Commissioner: Rs 5,000 + Rs 500/day; Section 251(1) - failure to give notice of intention to erect: Rs 500; Section 252 - failure to give notice for additions: Rs 500 + Rs 50/day; Section 255(4) - commencement of work without notice: Rs 2,000 + Rs 200/day; Section 257: Rs 500 + Rs 50/day; Section 258(1): Rs 1,000 + Rs 50/day; Section 258(2) - erection within regular line of street or in contravention of scheme/plan: Rs 1,000; Section 260 - inflammable material: Rs 1,000; Section 261 - failure to demolish buildings erected without sanction or erection in contravention of order: Rs 2,000 + Rs 200/day; Section 262 - erection in contravention of conditions of sanction etc.: Rs 2,000 + Rs 200/day; Section 263 - failure to carry out alterations: Rs 2,000; Section 264(1)-(2) - completion certificate / occupation: Rs 500 + Rs 50/day; Section 265(1) - restrictions on user: Rs 1,000 + Rs 100/day; Section 265(2)-(3) - ruinous structures: Rs 2,000 + Rs 200/day; Section 266(1) - failure to vacate dangerous building: Rs 1,000 + Rs 100/day; Section 284 - demolition of building unfit for habitation: Rs 2,000 + Rs 200/day; Section 407 - removal/defacing of notice: Rs 500; Section 408 - encroachment on land vested in the Corporation: Rs 500.


### Haryana Building Code, 2017

**Section 1.2(xxv) - Definition - 'Competent Authority'**

"Competent Authority" shall mean an officer/agency duly authorized;

> Note: Within municipal limits the Commissioner, Municipal Corporation (and officers delegated by him) is the Competent Authority for building plan sanction under the HMC Act 1994.

**Section 2.1(1) - Application for erection or re-erection of building**

Any person who intends to erect, re-erect or make alteration in any place in a building or demolish any building shall give notice in writing to the Competent Authority of his/her intention in the Form BR-I, accompanied by the documents specified (ownership documents, plans, structural drawings, certificates of the Architect/Engineer, etc.).

**Section 2.1(2) - Duty of Architect/Engineer to report violations**

Every person applying under Code 2.1(1) shall appoint an Architect/Engineer for drawing up of building plans/structural drawings and for the supervision of erection or re-erection of the building. ... During construction if appointed Architect/Engineer notices that violation (except compoundable) are going on he shall intimate the owner and advise him to stop further construction and remove the violation, will also intimate to the concerned authority.

**Section 2.2(3) - Self-certification - right to check and rectification of violations**

Competent Authority or any other person authorized by him reserves the right to check the building plans and construction at any stage and violations (except compoundable ones), if found shall have to be rectified by the owner/applicant. In case the owner/applicant fail to rectify violations, the Competent Authority may take necessary steps to remove the violations. Action shall also be taken against the defaulting Architect by referring his case to the Council of Architecture for misconduct and debarring/blacklisting the Architect from doing practice in State Government Departments/Authorities. All rectifications shall be at the risk and cost of the owner and no plea of the owner shall be entertained for any default committed by the Architect engaged by him. In all such cases the procedure of self-certification shall stand aborted.

**Section 2.2(4) - Notice to alter or demolish building erected in contravention**

If a building is erected or re-erected or construction work is commenced in contravention to any of the building regulations, the Competent Authority or any other person authorized by him shall be competent to require the building to be altered or demolished, by a written notice delivered to the owner. Such notice shall also specify the period during which such alteration or demolition has to be completed and if the notice is not complied with, the Competent Authority or any other person authorized by him may demolish the said building at the expense of the owner.

**Section 4.3-4.4 - Validity and re-validation of sanctioned plans** *(verify against Gazette)*

The sanction of building plans remains valid for the period specified in the Code (two years, extendable by re-validation on payment of the prescribed fee); construction continued after expiry of validity without re-validation is construction without a valid sanction.

> Note: Summary. Verbatim validity periods to be confirmed from Codes 4.3 and 4.4 of the current HBC.

**Section 4.5 - Deemed sanction**

The Competent Authority shall pass an order within a period of twenty days of submission of building plans, accompanied by all necessary documents as mentioned in Code 2.1, either sanctioning or rejecting it. The building plan shall be deemed to be sanctioned, if it is in conformity with building Code and in accordance with the permitted land use of the area and all leviable fee/charges have been deposited by the applicant but no orders have been passed by the Competent Authority within the specified time.

**Section 4.6 - Submission of revised building plans during the validity period of sanction**

(1) If during the construction of a building, any deviation from the sanctioned plan is intended to be made, approval of the Competent Authority for the same may be obtained before the change is made. The revised plan showing the deviations shall be submitted and the procedure laid down for the sanction of building plan as stated in Code No. 2.1 and 2.2, shall be followed for all revised plans, along with the depositing balance scrutiny fee, if any. (2) Any notice and building approval is not necessary for compoundable alterations/violations, which do not otherwise violate any provisions regarding general building requirements, structural stability and fire safety requirements of this building Code.

**Section 4.7 - Revocation of sanction**

The sanction granted under Code 4.2 can be revoked by the Competent Authority, if it is found that such sanction has been obtained by the owner by misrepresentation of material facts or fraudulent document submitted along with the building plan application or otherwise or the construction is not being done in accordance with the sanction granted.

**Section 4.9 - Damp Proof Course (DPC) certificate** *(verify against Gazette)*

The owner (or the Architect, in case of self certification) shall submit a certificate that the construction of building up to DPC level is in accordance with the sanctioned plan before proceeding further.

**Section 4.10(2) - Occupation Certificate mandatory before occupation**

No owner/applicant shall occupy or allow any other person to occupy new building or part of a new building or any portion whatsoever, until such building or part thereof has been certified by the Competent Authority or by any officer authorized by him in this behalf as having been completed in accordance with the permission granted and an 'Occupation Certificate' has been issued in Form BR-VII. However, Competent Authority may also seek composition charges of compoundable violations which are compoundable before issuance of Form BR-VII. Further, the water, sewer and electricity connection be released only after issuance of said occupation certificate by the Competent Authority.

**Section 4.11(2) - Self-certified occupation - non-compoundable violations**

Provided, if any violation found within time prescribed above during inspection, which is not listed in compoundable violations stated at Code 4.11(1)(i), then the violation be compounded (or demolished if it is non-compoundable), as per composition charges prescribed by the Competent Authority.

**Section 4.12 - Revocation of Occupation certificate**

In case, after the issuance of occupation certificate, if found at any stage that the building is used for some other purpose against the permission or make any addition/alteration in the building then, after affording personal hearing to the owner, the Competent Authority may pass orders for revocation of occupation permission and the same shall be restored only after removal of violations.

**Section 6.2(1)-(2) - Sub-division and amalgamation of plots**

(1) Division of plot into smaller units is permissible in core areas with the prior approval of the Competent Authority. Each such plot shall be accessible separately and independently through a public road laid out and constructed to the satisfaction of the Competent Authority. (2) Except as otherwise expressly provided at the time of sale of a plot, not more than one building unit shall be erected on any one plot, but two or more plots may be amalgamated for purpose of erection of one "building unit". In case of back to back plots which are to be amalgamated, two building units may be allowed maintaining the rear setbacks intact subject to the condition that a maximum of four dwelling units shall be permissible on the amalgamated plot.

**Section 6.3 - Proportion of the site which may be covered with buildings (ground coverage, FAR, height, setbacks)**

The proportions of covered area of a building, including ancillary buildings, shall be in accordance with the plot categories given in the sub-Codes and the remaining portion shall be left open in the form of open space around the building. ... The stilts are permitted for parking purposes in residential and commercial plots of all sizes, subject to the condition that maximum permissible height of building shall not exceed 15 metres. ... Any violation of the permissible ground coverage limit as indicated in the table shall be non-compoundable.

> Note: Permissible ground coverage, FAR, height and setback tables are in Code 6.3 (residential plotted), 6.4 (architectural control) and the use-specific chapters. The inspection form captures measured vs permitted values.

**Section 7.1 - Parking** *(verify against Gazette)*

Parking shall be provided as per the norms of the Code; stilt/basement parking areas shall be used only for parking.

**Section 7.16 - Basement** *(verify against Gazette)*

Basement construction is permitted only as per the Code (extent, use, setbacks, structural safety and drainage conditions).

**Section 7.17 - Fire safety** *(verify against Gazette)*

Fire safety requirements (means of egress, fire NOC for buildings above the prescribed height) as per the Code and the Haryana Fire and Emergency Services Act.


### Haryana Public Premises and Land (Eviction and Rent Recovery) Act, 1972

**Section 2(c) - Definition - 'premises'**

"premises" means any land, whether used for agricultural or non-agricultural purposes, or any building or part of a building and includes,- (i) the garden, grounds and out-houses, if any, appertaining to such building or part of a building; and (ii) any fittings affixed to such building or part of a building for the more beneficial enjoyment thereof;

**Section 2(e) - Definition - 'public premises'**

"public premises" means any premises belonging to, or taken on lease or requisitioned by, or on behalf of, the State Government, or requisitioned by the competent authority under the Punjab Requisitioning and Acquisition of Immovable Property Act, 1953, and includes any premises belonging to any local authority, or District Soldiers, Sailors and Airmen's Board or any university established by law or any Corporation or Board owned or controlled by the State Government;

> Note: 'Local authority' includes the Municipal Corporation; hence municipal land is also 'public premises' and the Collector's HPPA route is available in addition to s.408A HMC Act.

**Section 3 - Unauthorised occupation of public premises**

For the purposes of this Act, a person shall be deemed to be in unauthorised occupation of any public premises- (a) where he has, whether before or after the commencement of this Act, entered into possession thereof otherwise than under and in pursuance of any allotment, lease or grant; or (b) where he, being an allottee, lessee or grantee, has, by reason of the determination or cancellation of his allotment, lease or grant in accordance with the terms in that behalf therein contained, ceased, whether before or after the commencement of this Act, to be entitled to occupy or hold such public premises; or (c) where any person authorised to occupy any public premises has, whether before or after the commencement of this Act,- (i) sub-let, in contravention of the terms of allotment, lease or grant, without the permission of the State Government or of any other authority competent to permit such sub-letting, the whole or any part of such public premises, or (ii) otherwise acted in contravention of any of the terms, express or implied, under which he is authorised to occupy such public premises. Explanation.- For the purposes of clause (a), a person shall not merely by reason of the fact that he has paid any rent be deemed to have entered into possession as allottee, lessee or grantee.

**Section 4 - Issue of notice to show cause against order of eviction**

(1) If the Collector is of opinion that any persons are in unauthorised occupation of any public premises situate within his jurisdiction and that they should be evicted, the Collector shall issue, in the manner hereinafter provided, a notice in writing calling upon all persons concerned to show cause why an order of eviction should not be made. (2) The notice shall- (a) specify the grounds on which the order of eviction is proposed to be made; and (b) require all persons concerned, that is to say, all persons who are, or may be, in occupation of, or claim interest in, the public premises, to show cause, if any, against the proposed order on or before such date as is specified in the notice, being a date not earlier than ten days from the date of issue thereof. (3) The Collector shall cause the notice to be affixed on the outer door or some other conspicuous part of the public premises, or of the estate in which the public premises are situate, and in such other manner as may be prescribed, whereupon the notice shall be deemed to have been duly given to all persons concerned. (4) Where the Collector knows or has reasons to believe that any persons are in occupation of the public premises, then without prejudice to the provisions of sub-section (3), he shall cause a copy of the notice to be served on every such person by post or by delivering or tendering it to that person or in such other manner as may be prescribed.

**Section 5 - Eviction of unauthorised persons**

(1) If, after considering the cause, if any, shown by any person in pursuance of a notice under section 4 and any evidence he may produce in support of the same and after giving him a reasonable opportunity of being heard, the Collector is satisfied that the public premises are in unauthorised occupation, the Collector may make an order of eviction, for reasons to be recorded therein, directing that the public premises shall be vacated, on such date as may be specified in the order, by all persons who may be in occupation thereof or any part thereof, and cause a copy of the order to be affixed on the outer door or some other conspicuous part of the public premises or of the estate in which the public premises are situate. (2) If any person refuses or fails to comply with the order of eviction within thirty days of the date of its publication under sub-section (1), the Collector or any other officer duly authorised by him in this behalf may evict that person from, and take possession of, the public premises and may, for that purpose, use such force as may be necessary.

**Section 6(1) - Disposal of property left on public premises by unauthorised occupants**

Where any persons have been evicted from any public premises under section 5, the Collector may, after giving fourteen days notice to the persons from whom possession of the public premises has been taken and after publishing the notice in at least one newspaper having circulation in the locality, remove or cause to be removed or sell by public auction any property remaining on such premises.

**Section 7(2)-(3) - Power to recover damages for unauthorised occupation**

(2) Where any person is, or has at any time been, in unauthorised occupation of any public premises, the Collector may, having regard to such principles of assessment of damages as may be prescribed, assess the damages on account of the use and occupation of such premises and may, by order, require that person to pay the damages within such time and in such instalments as may be specified in the order. (3) No order under sub-section (1) or sub-section (2) shall be made against any person until after the issue of a notice in writing to the person calling upon him to show cause within such time as may be specified in the notice, why such order should not be made, and until his objections, if any, and any evidence he may produce in support of the same, have been considered by the Collector.

**Section 9 - Appeals**

(1) An appeal shall lie from every order of the Collector made in respect of any public premises under section 5 or section 7 to the Commissioner. (2) An appeal under sub-section (1) shall be preferred,- (a) in the case of an appeal from an order under section 5, within thirty days from the date of publication of the order under sub-section (1) of that section; and (b) in the case of an appeal from an order under section 7, within thirty days from the date on which the order is communicated to the appellant: Provided that the Commissioner may entertain the appeal after the expiry of the said period of thirty days if he is satisfied that the appellant was prevented by sufficient cause from filing the appeal in time. (3) Where an appeal is preferred from an order of the Collector, the Commissioner may stay the enforcement of that order for such period and on such conditions as he deems fit. (4) Every appeal under this section shall be disposed of by the Commissioner as expeditiously as possible. (5) The costs of any appeal under this section shall be in the discretion of the Commissioner.

> Note: 'Commissioner' here is the Divisional Commissioner (s.2 read with the Punjab Land Revenue Act).

**Section 10 - Finality of orders**

Save as otherwise expressly provided in this Act, every order made by the Collector or Commissioner under this Act shall be final and shall not be called in question in any original suit, application or execution proceeding and no injunction shall be granted by any court or other authority in respect of any action taken or to be taken in pursuance of any power conferred by or under this Act.

**Section 11(1) - Offence of re-occupation after eviction** *(verify against Gazette)*

If any person who has been evicted from any public premises under this Act again occupies the premises without authority for such occupation he shall be punishable with imprisonment for a term which may extend to one year, or with fine which may extend to one thousand rupees, or with both.

**Section 14 - Recovery of rent, damages and costs as arrears of land revenue**

If any person refuses or fails to pay the arrears of rent payable under sub-section (1) of section 7 or the damages payable under sub-section (2) of that section or the costs awarded to the State Government or the local authority under sub-section (5) of section 9 or any portion of such rent, damages or costs, within the time, if any, specified therefor in the order relating thereto, the Collector shall proceed to recover the amount due as arrears of land revenue.

**Section 15 - Bar of jurisdiction of civil courts**

No court shall have jurisdiction to entertain any suit or proceeding in respect of the eviction of any person who is in unauthorised occupation of any public premises or the recovery of the arrears of rent payable under sub-section (1) of section 7 or the damages payable under sub-section (2) of that section or the costs awarded to the State Government or the local authority under sub-section (5) of section 9 or any portion of such rent, damages or costs.


### Punjab Scheduled Roads and Controlled Areas Restriction of Unregulated Development Act, 1963

**Section 3 - Restriction on erection of buildings along scheduled roads** *(verify against Gazette)*

No person shall erect or re-erect any building or make or extend any excavation or lay out any means of access to a road within the restricted belt along a scheduled road except with the permission of the Director, Town and Country Planning.

> Note: Summary.

**Section 7 - Restriction on use of land in controlled areas** *(verify against Gazette)*

No person shall, in a controlled area, erect or re-erect any building, make or extend any excavation, lay out any means of access to a road, or use land for any purpose other than the one for which it was used on the date of publication of the notification, except with the permission (Change of Land Use) of the Director.

> Note: Summary.

**Section 12(1) - Offences and penalties** *(verify against Gazette)*

Any person who erects or re-erects any building or makes or extends any excavation or lays out any means of access to a road in contravention of sections 3 or 6 or of any conditions imposed by an order under sections 8 or 10, or uses any land in contravention of section 7 or 10, shall be punishable with imprisonment of either description for a term which may extend to three years and shall also be liable to fine which may extend to fifty thousand rupees but shall not be less than ten thousand rupees, and in the case of a continuing contravention, with a further fine which may extend to one thousand rupees for every day during which the contravention continues after conviction for the first such contravention.

> Note: Summary of the amended provision (amended up to 2018).

**Section 12(2)-(3) - Restoration / demolition by the Director** *(verify against Gazette)*

(2) The Director may issue a notice calling upon the person to stop the construction/use and to appear and show cause within seven days why the land/building should not be restored to its original state; on failure the Director may pass an order of restoration (demolition). (3) If the order is not complied with within seven days, the Director may himself take the measures (including demolition) and recover the cost as arrears of land revenue; where the contravention continues during the show-cause period the Director may act at once.

> Note: Summary.

**Section 12A - Duty of police officers** *(verify against Gazette)*

It shall be the duty of every police officer to communicate information regarding the design or commission of offences under the Act to the Director and to assist the Director and officers authorised by him in the lawful exercise of their powers.

> Note: Summary.


### Bharatiya Nyaya Sanhita, 2023

**Section 223 - Disobedience to order duly promulgated by public servant** *(verify against Gazette)*

Whoever, knowing that, by an order promulgated by a public servant lawfully empowered to promulgate such order, he is directed to abstain from a certain act, or to take certain order with certain property in his possession or under his management, disobeys such direction, shall, if such disobedience causes or tends to cause obstruction, annoyance or injury, or risk of obstruction, annoyance or injury, to any person lawfully employed, be punished with simple imprisonment for a term which may extend to six months, or with fine which may extend to two thousand five hundred rupees, or with both.

> Note: Successor to IPC s.188. Quoted in stop-work / sealing orders as the consequence of disobedience.

**Section 221 - Obstructing public servant in discharge of public functions** *(verify against Gazette)*

Whoever voluntarily obstructs any public servant in the discharge of his public functions, shall be punished with imprisonment of either description for a term which may extend to three months, or with fine which may extend to two thousand five hundred rupees, or with both.

> Note: Successor to IPC s.186.


### Haryana Municipal Corporation Act, 1994

**Section 216 - Vesting of public streets in Corporation**

(1) All streets within the Municipal area which are or at any time have become public streets, and the pavements, stones and other materials thereof, shall vest in the Corporation. (2) All public streets vesting in the Corporation shall be under the control of the Commissioner and shall be maintained, controlled and regulated by him in accordance with the bye-laws made in this behalf.

**Section 230 - Owner's obligation when dealing with land as building sites** *(verify against Gazette)*

Every person who intends to sell, lease or otherwise dispose of land as building sites, or to lay out private streets, shall obtain sanction of the layout plan from the Commissioner before doing so.

> Note: Summary.

**Section 231 - Sanction of layout / private streets** *(verify against Gazette)*

Layout plans of land intended to be used as building sites and private streets require sanction of the Commissioner under this section.

> Note: Summary.

**Section 232 - Alteration or demolition of street made in breach of section 231** *(verify against Gazette)*

The Commissioner may by notice require the alteration or demolition of any private street laid out in breach of section 231 and, on non-compliance, may himself alter or demolish it and recover the expenses.

> Note: Summary.

**Section 252(1)(e) - Works within regular line of street**

To repair, remove, construct, reconstruct, or make any addition to or structural alteration in any portion of a building abutting on a street which stands within the regular line of such street - requires sanction under section 252.

**Section 254(2)(d) - Ground of refusal - layout not sanctioned**

That in cases falling under section 230, lay out plans have not been sanctioned in accordance with section 231.

**Section 254(2)(e) - Ground of refusal - encroachment on Government / Corporation land**

That the building or work would be an encroachment on Government land or land vested in the Corporation.

**Section 254(2)(g) - Ground of refusal - contravention of building scheme**

That the building or work would be in contravention of any scheme sanctioned under section 267.

**Section 255(2) - Obligation to build in accordance with sanction**

Where a building or work is sanctioned or is deemed to have been sanctioned by the Commissioner under sub-section (1), the person who has given the notice shall be bound to erect the building or execute the work in accordance with such sanction but not so as to contravene any of the provisions of this Act or any other law or of any bye-law made thereunder.

**Section 255(3) - Fresh sanction if work not commenced within one year**

If the person or any one lawfully claiming under him does not commence the erection of the building or the execution of the work within one year of the date on which the building or work is sanctioned or is deemed to have been sanctioned, he shall have to give notice under section 252 or, as the case may be, under section 251 for fresh sanction.

**Section 255(4) - Notice of commencement**

Before commencing the erection of a building or execution of a work within the period specified in sub-section (3), the person concerned shall give notice to the Commissioner of the proposed date of the commencement of the erection of the building or the execution of the work.

> Third Schedule: Rs 2,000 + Rs 200/day

**Section 267 - Building Scheme** *(verify against Gazette)*

The Corporation may, and if so required by the Government shall, draw up a building scheme for built areas and a town planning scheme for unbuilt areas, which may provide for the restriction of the erection or re-erection of buildings, building lines, and the use to which buildings may be put.

> Note: Summary.

**Section 282 - Power of Commissioner to require improvement of building unfit for human habitation**

(1) Where the Commissioner upon information in his possession is satisfied that any building is in any respect unfit for human habitation, he may, unless in his opinion the building is not capable at a reasonable expense of being rendered fit, serve upon the owner of the building a notice requiring him within such time not being less than thirty days as may be specified in the notice to execute the works of improvement specified therein and stating that in his opinion those works will render the building fit for human habitation.

> Third Schedule: Rs 1,000


### Haryana Building Code, 2017

**Section 3.5 - Constructing building as per Architectural Control Sheet** *(verify against Gazette)*

Where an Architectural Control Sheet / zoning plan has been approved for a site, the building shall be constructed in conformity with it.

> Note: Summary.

**Section 6.1 - Use of site, type and character of building** *(verify against Gazette)*

No site shall be used for a purpose other than that for which it is designated in the Development Plan / zoning plan; the type and character of the building shall conform to the permitted land use.

> Note: Summary.

**Section 6.4 - Architectural / Frame Control and siting of building** *(verify against Gazette)*

Siting of buildings and frame control as per the approved zoning / architectural control of the area.

> Note: Summary.

**Section 7.12 - Cantilevered roof and chajja projections** *(verify against Gazette)*

Chajjas and cantilevered projections are permitted only to the extent specified in the Code and shall not project over public land beyond the permitted limits.

> Note: Summary.

**Section 7.13 - Mezzanine floor** *(verify against Gazette)*

Mezzanine floors are permitted only as per the area and height limits of the Code and are counted towards FAR as specified.

> Note: Summary.
