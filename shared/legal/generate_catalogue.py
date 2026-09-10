#!/usr/bin/env python3
"""
Generates the two JSON files that are the single source of truth for the legal
framework of the MCG Building Violation Management System (BVMS):

  legal_sections.json      - verbatim / near-verbatim statutory text, one record per section
  violation_catalogue.json - the violation types the field team can select, each mapped
                             to the sections above, the action provisions, penalties,
                             statutory timelines and the evidence checklist

Edit THIS file (not the JSON) when the law changes, then run:
    python3 generate_catalogue.py

Sources (all copies kept in docs/legal-sources/):
  * Haryana Municipal Corporation Act, 1994 (Haryana Act 16 of 1994) - bare act
    (latestlaws.com PDF) + Haryana Govt. Gazette (Extra.) 26.09.2013 (Act 12 of 2013,
    inserting s.263A) from archive.org (1994HR16).
  * Haryana Building Code, 2017 with amendments up to 25.05.2023 (tcpharyana.gov.in).
  * Haryana Public Premises and Land (Eviction and Rent Recovery) Act, 1972 (archive.org 1972HR24).
  * Punjab Scheduled Roads and Controlled Areas Restriction of Unregulated Development
    Act, 1963 (as applicable to Haryana) - summary only.
Text extracted from scanned PDFs was cleaned by hand; where OCR was doubtful the
record carries "verify": true so the Legal Branch can confirm against the Gazette.
"""
import json, os, datetime

HERE = os.path.dirname(os.path.abspath(__file__))

# ----------------------------------------------------------------------------
# 1. STATUTES AND SECTIONS
# ----------------------------------------------------------------------------
HMCA = "HMCA1994"
HBC = "HBC2017"
HPPA = "HPPA1972"
PSRCA = "PSRCA1963"
BNS = "BNS2023"

def sec(code, section, heading, text, kind="substantive", verify=False, notes=None, fine=None, daily_fine=None):
    d = {
        "statute": code,
        "section": section,
        "heading": heading,
        "kind": kind,  # definition | substantive | procedure | penalty | appeal | schedule | delegation
        "text": " ".join(text.split()),
    }
    if verify: d["verify"] = True
    if notes: d["notes"] = notes
    if fine is not None: d["schedule_fine_inr"] = fine
    if daily_fine is not None: d["schedule_daily_fine_inr"] = daily_fine
    return d

sections = []

# ---- Haryana Municipal Corporation Act, 1994 --------------------------------
sections += [
sec(HMCA, "2(2)", "Definition - 'building'",
    """"building" means a shop, house, out-house, stable, latrine, urinal, shed, hut, well or any other structure whether of masonry, bricks, wood, mud, metal or other material and includes a well but does not include any portable shelter;""", "definition"),
sec(HMCA, "2(4A)", "Definition - 'competent authority'",
    """"competent authority" means the Joint Commissioner of Corporation.""", "definition",
    notes="Inserted by amendment; makes the Joint Commissioner the competent authority for eviction/demolition on Corporation land under s.408A."),
sec(HMCA, "2(22)", "Definition - 'land'",
    """"land" includes benefits that arise out of land, things attached to the earth or permanently fastened to anything attached to the earth and rights created by law over any street;""", "definition"),
sec(HMCA, "2(33)", "Definition - 'occupier'",
    """"occupier" includes- (a) any person who for the time being is paying or is liable to pay to the owner the rent or any portion of the rent of the land or building in respect of which such rent is paid or is payable; (b) an owner in occupation of, or otherwise using his land or building; (c) a rent-free tenant of any land or building; (d) a licensee in occupation of any land or building; and (e) any person who is liable to pay to the owner damage for the use and occupation of any land or building;""", "definition"),
sec(HMCA, "2(36)", "Definition - 'owner'",
    """"owner", (a) when used with reference to any building and land, includes - (i) the person who receives the rent thereof or who would be entitled to receive the rent thereof if the same were let; (ii) an agent or trustee who receives such rent on account of the owner; (iii) an agent or trustee who receives the rent of or is entrusted with or concerned for, any premises devoted to religious or charitable purposes; (iv) a receiver, or manager, appointed by any court of competent jurisdiction to have the charge of, or to exercise the rights of an owner of the said building or land; and (v) a mortgagee in possession;""", "definition", verify=True),
sec(HMCA, "2(37)", "Definition - 'premises'",
    """"premises" means any land or building or part of a building and includes - (a) the garden, ground and out-houses, if any, appertaining to a building or part of a building; and (b) any fitting affixed to a building or part of building for the more beneficial enjoyment thereof;""", "definition"),

sec(HMCA, "224", "Setting back building to regular line of streets",
    """Where a building is set back or set forward to the regular line of a public street, the Commissioner may require the building to be set back to the regular line of the street and no person shall erect or re-erect any portion of a building within the regular line of a public street except with the written permission of the Commissioner.""", "substantive", verify=True,
    notes="Paraphrase of ss.223-225 (regular line of streets). Use the bare act for verbatim text."),
sec(HMCA, "235(1)", "Prohibition of projection upon streets etc.",
    """Except as provided in section 236, no person shall erect, set-up, add to, or place against or in front of any premises any structure or fixture which will,- (a) overhang, jut or project into, or in any way encroach upon and obstruct in any way the safe or convenient passage of the public along any street, or (b) jut or project into or encroach upon any drain or open channel in any street so as in any way to interfere with the use or proper working of such drain or channel or to impede the inspection or cleansing thereof."""),
sec(HMCA, "235(2)", "Notice to remove projection",
    """The Commissioner may by notice require the owner or occupier of any premises to remove or to take such other action as he may direct in relation to any structure or fixture which has been erected, set-up, added to or placed against, or in front of, the said premises in contravention of this section.""", "procedure"),
sec(HMCA, "236", "Projections over streets may be permitted in certain cases",
    """(1) The Commissioner may give a written permission, on such terms and on payment of such fee as he in each case thinks fit, to the owner or occupier of the building or any street,- (a) to erect an arcade over such street or any portion thereof; or (b) to put up a verandah, balcony, arch, connecting passage, sunshade, weather frame, canopy, awning or other such structure or thing projecting from any storey over or across any street or portion thereof: Provided that no permission shall be given by the Commissioner for the erection of an arcade in any public street in which construction of an arcade has not been generally sanctioned by the Corporation. (2) The Commissioner may at any time by notice require the owner or occupier of any building to remove a verandah, balcony, sunshade, weather frame or the like put up in accordance with the provisions of this Act and such owner or occupier shall be bound to take action accordingly but shall be entitled to compensation for the loss caused to him by such removal and the cost incurred thereon.""", fine=500, daily_fine=50),
sec(HMCA, "238(1)", "Prohibition of structures, fixtures or deposit of things in streets",
    """No person shall, except with the permission of the Commissioner granted in this behalf, erect or set-up any wall, fence, rail, post, step, booth or other structure whether fixed or movable or whether of a permanent or temporary nature, or any fixture in or upon any street or upon or over any open channel, drain, well or tank in any street so as to form an obstruction to or an encroachment upon, or projection over, or to occupy any portion of such street, channel, drain, well or tank.""", fine=1000, daily_fine=100),
sec(HMCA, "238(2)", "Deposit of things in streets",
    """No person shall, except with the permission of the Commissioner and on payment of such fee as he in each case thinks fit, place or deposit upon any street, or upon any open channel, drain or well in any street or upon any public place any stall, chair, bench, box, ladder, bale or other thing whatsoever so as to form an obstruction thereto or encroachment thereon.""", fine=500),
sec(HMCA, "240", "Power to remove anything deposited or exposed for sale in contravention of this Act",
    """The Commissioner may, without notice, cause to be removed- (a) any stall, chair, bench, box, ladder, bale or other thing whatsoever placed, deposited, projected, attached or suspended in, upon, from or to any place in contravention of this Act; (b) any article whatsoever hawked or exposed for sale on any public place in contravention of this Act and any vehicle, package, box or any other thing in or on which such article is placed.""", "procedure"),
sec(HMCA, "243(1)", "Streets not to be opened or broken up and building materials not to be deposited therein without permission",
    """No person other than the Commissioner or a Corporation Officer or other Corporation employee shall, without the written permission of the Commissioner- (a) open, break up, displace, take up or make any alteration in, or cause any injury to the soil or pavement or any wall, fence, post, chain or other material or thing forming part of any street; or (b) deposit any building material in any street; or (c) set up in any street any scaffold or any temporary erection for the purpose of any work whatever, or any posts, bars, rails, boards or other things by way of an enclosure, for the purpose of making mortar or depositing bricks, lime, rubbish or other materials.""", fine=500, daily_fine=50),
sec(HMCA, "243(3)", "Removal of material deposited without permission",
    """The Commissioner may, without notice, cause to be removed any of the things referred to in clause (b) or clause (c) of sub-section (1) which has been deposited or set up in any street without the permission specified in that sub-section or which having been deposited or set up with permission has not been removed within the period specified in the notice issued under sub-section (2).""", "procedure"),
sec(HMCA, "244", "Disposal of things removed under this Chapter",
    """(1) Any of the things caused to be removed by the Commissioner under this Chapter shall, unless the owner thereof turns up to take back such things and pays to the Commissioner the charges for the removal and storage of such things, be disposed of by public auction or in such other manner and within such time as the Commissioner thinks fit. (2) The charges for removal and storage of the things sold under sub-section (1) shall be paid out of the proceeds of the sale thereof and the balance, if any, shall be paid to the owner of the things sold on a claim being made therefor within a period of two years from the date of sale, and if no such claim is made within the said period, shall be credited to the Corporation.""", "procedure"),
sec(HMCA, "246(1)", "Commissioner to take steps for repairing or enclosing dangerous places",
    """If any place is, in the opinion of the Commissioner, for want of sufficient repair or protection or enclosure, or owing to some work being carried on thereupon, dangerous or causing inconvenience to passengers along a street or to other persons including the owner or occupier of the said place, who have legal access thereto or to the neighbourhood thereof, the Commissioner may by notice in writing require the owner or occupier of such place to repair, protect or enclose the same or take such other steps as shall appear to the Commissioner necessary in order to prevent the danger or inconvenience arising therefrom.""", fine=500, daily_fine=50),

sec(HMCA, "250", "Prohibition of erection of building without sanction",
    """No person shall erect or commence to erect any building or execute any of the works specified in section 252 except with the previous sanction of the Commissioner, nor otherwise than in accordance with the provisions of this Chapter and of the bye-laws made under this Act in relation to the erection of buildings or execution of works.""", fine=5000, daily_fine=500),
sec(HMCA, "251", "Erection of building - notice for sanction",
    """(1) Every person who intends to erect a building shall apply for sanction by giving notice in writing of his intention to the Commissioner in such form and containing such information as may be prescribed by bye-laws made in this behalf. (2) Every such notice shall be accompanied by such documents and plans as may be prescribed.""", fine=500),
sec(HMCA, "252", "Application for addition to, or repairs of building",
    """(1) Every person who intends to execute any of the following works, namely:- (a) to make any addition to a building; (b) to make any alteration or repairs to a building involving the removal or re-erection of any external or partition wall thereof or of any wall which supports the roof thereof to an extent exceeding one half of such wall above the plinth level, such half to be measured in superficial metres; (c) to make any alteration or repairs to a frame building involving the removal or re-erection of more than one half of the posts in any wall which support the roof thereof to an extent exceeding one half of such wall above the plinth level, such half to be measured in superficial metres; (d) to make any alteration in a building involving- (i) the sub-division of any room in such building so as to convert the same into two or more separate rooms; or (ii) the conversion of any passage or space in such building into a room or rooms; (e) to repair, remove, construct, reconstruct, or make any addition to or structural alteration in any portion of a building abutting on a street which stands within the regular line of such street; (f) to close permanently any door or window in an external wall; (g) to remove or reconstruct the principal staircase or to alter its position, shall apply for sanction by giving notice in writing of his intention to the Commissioner in such form and containing such information as may be prescribed by bye-laws made in this behalf. (2) Every such notice shall be accompanied by such documents and plans as may be so prescribed.""", fine=500, daily_fine=50),
sec(HMCA, "253", "Conditions of valid notice",
    """(1) A person giving the notice required by section 251 shall specify the purpose for which it is intended to use the building to which such notice relates, and a person giving the notice required by section 252 shall specify whether the purpose for which the building is being used is proposed or likely to be changed by the execution of the proposed work. (2) No notice shall be valid until the information required under sub-section (1) and any further information and plans which may be required by bye-laws made in this behalf have been furnished to the satisfaction of the Commissioner along with the notice.""", "procedure"),
sec(HMCA, "254", "Sanction or refusal of building or works",
    """(1) The Commissioner shall sanction the erection of a building or the execution of a work, unless such building or work would contravene any of the provisions of sub-section (2) of this section or of the provisions of section 258. (2) The grounds on which the sanction of a building or work may be refused shall be the following, namely:- (a) that the building or work, or the use of the site for the building or work or any of the particulars comprised in the site plan, ground plan, elevation section or specification would contravene the provisions of any bye-laws made in this behalf or of any other law or of any rule, bye-law or order made under such other law; (b) that the notice for sanction does not contain the particulars or is not prepared in the manner required under the bye-laws made in this behalf; (c) that any information or documents required by the Commissioner under this Act or any bye-laws made thereunder has or have not been duly furnished; (d) that in cases falling under section 230, lay out plans have not been sanctioned in accordance with section 231; (e) that the building or work would be an encroachment on Government land or land vested in the Corporation; (f) that the site of the building or work does not abut on a street or projected street and that there is no access to such building or work from any such street by a passage or pathway appertaining to such site; (g) that the building or work would be in contravention of any scheme sanctioned under section 267; (h) that the building for habitation does not provide for a flush or a water seal latrine. (3) The Commissioner shall communicate the sanction to the person who has given the notice, and where he refuses sanction on any of the grounds specified in sub-section (2) of this section or under section 258 he shall record a brief statement of his reasons for such refusal and communicate the refusal along with the reasons therefor to the person who has given the notice. (4) The sanction or refusal as aforesaid shall be communicated in such manner as may be specified in the bye-laws made in this behalf."""),
sec(HMCA, "255", "When building or work may be proceeded with",
    """(1) Where within a period of sixty days after the receipt of any notice under section 251 or section 252 or of the further information, if any, required under section 253 the Commissioner does not refuse to sanction the building or work or upon refusal does not communicate the refusal to the person who has given the notice, the Commissioner shall be deemed to have accorded sanction to the building or work and the person by whom the notice has been given shall be free to commence and proceed with the building or work in accordance with his intention as expressed in the notice and the documents and plans accompanying the same: Provided that if it appears to the Commissioner that the site of the proposed building or work is likely to be affected by any scheme of acquisition of land for any public purpose or by any proposed regular line of a public street or extension, improvement, widening or alteration of any street, the Commissioner may withhold sanction of the building or work for such period not exceeding three months as he deems fit and the period of sixty days shall be deemed to commence from the date of the expiry of the period for which the sanction has been withheld. (2) Where a building or work is sanctioned or is deemed to have been sanctioned by the Commissioner under sub-section (1), the person who has given the notice shall be bound to erect the building or execute the work in accordance with such sanction but not so as to contravene any of the provisions of this Act or any other law or of any bye-law made thereunder. (3) If the person or any one lawfully claiming under him does not commence the erection of the building or the execution of the work within one year of the date on which the building or work is sanctioned or is deemed to have been sanctioned, he shall have to give notice under section 252 or, as the case may be, under section 251 for fresh sanction of the building or the work and the provisions of this section shall apply in relation to such notice as they apply in relation to the original notice. (4) Before commencing the erection of a building or execution of a work within the period specified in sub-section (3), the person concerned shall give notice to the Commissioner of the proposed date of the commencement of the erection of the building or the execution of the work: Provided that if the commencement does not take place within seven days of the date so notified the notice shall be deemed not to have been given and a fresh notice shall be necessary in this behalf.""", fine=2000, daily_fine=200,
    notes="Third Schedule fine shown is for s.255(4) (commencement of work without notice)."),
sec(HMCA, "256", "Sanction accorded under misrepresentation",
    """If at any time after the sanction of any building or work has been accorded, the Commissioner is satisfied that such sanction was accorded in consequence of any material misrepresentation or fraudulent statement contained in the notice given or information furnished under sections 251, 252 and 253 he may by order in writing, cancel for reasons to be recorded such sanction and any building or work commenced, erected, or done shall be deemed to have been commenced, erected or done without such sanction: Provided that before making any such order the Commissioner shall give reasonable opportunity to the person affected as to why such order should not be made."""),
sec(HMCA, "258(2)", "Buildings within regular line of street or in contravention of scheme",
    """The erection of any such building or the execution of any such work may be refused by the Commissioner if such building or any portion thereof or such work comes within the regular line of any street, the position and direction of which has been laid down by the Commissioner but which has not been actually constructed or if such building or any portion thereof or such work is in contravention of any building or any other scheme or plan prepared under this Act, or any other law for the time being in force.""", fine=1000),
sec(HMCA, "259", "Period for completion of building or work",
    """The Commissioner when sanctioning the erection of a building or execution of a work, shall specify a reasonable period after the commencement of the building or work within which the building or work is to be completed and if the building or work is not completed within the period so specified it shall not be continued thereafter without fresh sanction obtained in the manner hereinbefore provided, unless the Commissioner on application made therefor, has allowed an extension of that period."""),
sec(HMCA, "260", "Prohibition against use of inflammable materials for buildings etc. without permission",
    """In such areas as may be specified by bye-laws made in this behalf, no roof, verandah, pandal or wall of a building or no shed or fence shall be constructed or reconstructed of cloth, grass, leaves, mats or other inflammable material except with the written permission of the Commissioner nor shall any such roof, verandah, pandal, wall, shed, fence constructed or reconstructed in any year be retained in a subsequent year except with fresh permission obtained in this behalf.""", fine=1000),
sec(HMCA, "261(1)", "Order of demolition and stoppage of building and works in certain cases - show cause and demolition order",
    """Where the erection of any work has been commenced, or is being carried on or has been completed without or contrary to the sanction referred to in section 254 or in contravention of any condition subject to which such sanction has been accorded or in contravention of any of the provisions of this Act, or bye-laws made thereunder, the Commissioner may in addition to any other action that may be taken under this Act, make an order directing that such erection or work shall be demolished by the person at whose instance the erection or work has been commenced or is being carried on or has been completed within such period (not being less than three days from the date on which copy of the order of demolition with a brief statement of the reasons therefor has been delivered to that person) as may be specified in the order of demolition: Provided that no order of demolition shall be made unless the person has been given by means of a notice served in such manner as the Commissioner may think fit, a reasonable opportunity of showing cause why such order should not be made: Provided further that where the erection or work has not been completed the Commissioner may by the same order or by a separate order, whether made at the time of the issue of the notice under the first proviso or at any other time, direct the person to stop the erection or work until the expiry of the period within which an appeal against the order of demolition, if made, may be preferred under sub-section (2).""", fine=2000, daily_fine=200),
sec(HMCA, "261(2)", "Appeal against demolition order",
    """Any person aggrieved by an order of the Commissioner made under sub-section (1) may prefer an appeal against the order to the Divisional Commissioner within the period specified in the order for the demolition of the erection or work to which it relates.""", "appeal",
    notes="Words 'court of the District Judge' substituted by 'Divisional Commissioner' by Haryana Act 1 of 2007 (w.e.f. 14.02.2007). The latestlaws PDF still shows 'District Judge' in sub-section (2) but 'Divisional Commissioner' in (3)-(6); the appellate authority is the Divisional Commissioner.", verify=True),
sec(HMCA, "261(3)", "Stay of demolition order on appeal",
    """Where an appeal is preferred under sub-section (2) against an order of demolition the Divisional Commissioner may stay the enforcement of that order on such terms, if any, and for such period, as it may think fit: Provided that where the erection of any building or execution of any work has not been completed at the time of the making of the order of demolition, no order staying the enforcement of the order of demolition shall be made by the Divisional Commissioner unless security, sufficient in the opinion of the Divisional Commissioner, has been given by the appellant for not proceeding with such erection or work pending the disposal of the appeal.""", "appeal"),
sec(HMCA, "261(4)", "Bar of suits / injunctions",
    """Save as provided in this section no court shall entertain any suit, application or other proceeding for injunction or other relief against the Commissioner or restrain him from taking any action or making any order in pursuance of the provisions of this section.""", "appeal"),
sec(HMCA, "261(5)", "Finality of order",
    """Every order made by the Divisional Commissioner on appeal and subject only to such order, the order of demolition made by the Commissioner shall be final and conclusive.""", "appeal"),
sec(HMCA, "261(6)", "Execution of demolition order by the Commissioner and recovery of cost",
    """Where no appeal has been preferred against an order of demolition made by the Commissioner under sub-section (1) or where an order of demolition made by the Commissioner under that sub-section has been confirmed on appeal, whether with or without variation, the person against whom the order has been made shall comply with the order within the period specified therein or, as the case may be, within the period, if any, fixed by the Divisional Commissioner on appeal, and on the failure of the person to comply with the order within such period, the Commissioner may himself cause the erection or the work to which the order relates to be demolished and the expenses of such demolition shall be recoverable from such person as an arrear of tax under this Act.""", "procedure"),
sec(HMCA, "262(1)", "Order of stoppage of building or works in certain cases (stop-work order)",
    """Where the erection of any building or execution of any work has been commenced or is being carried on (but has not been completed) without or contrary to the sanction referred to in section 254 or in contravention of any condition subject to which such sanction has been accorded or in contravention of any provisions of this Act or bye-laws made thereunder, the Commissioner may in addition to any other action that may be taken under this Act by order, require the person at whose instance the building or the work has been commenced or is being carried on, to stop the same forthwith.""", fine=2000, daily_fine=200),
sec(HMCA, "262(2)", "Police assistance to enforce stop-work order",
    """If an order made by the Commissioner under section 261 or under sub-section (1) of this section directing any person to stop the erection of any building or execution of any work is not complied with, the Commissioner may require any police officer to remove such person and all his assistants and workmen from the premises within such time as may be specified in the requisition and such police officer shall comply with the requisition accordingly.""", "procedure"),
sec(HMCA, "262(3)", "Deputation of watch on premises",
    """After the requisition under sub-section (2) has been complied with, the Commissioner may, if he thinks fit, depute by a written order a police officer or a Corporation officer or other Corporation employee to watch the premises in order to ensure that the erection of the building or the execution of the work is not continued.""", "procedure"),
sec(HMCA, "262(4)", "Cost of watch recoverable",
    """Where a police officer or a Corporation Officer or other Corporation employee has been deputed under sub-section (3) to watch the premises, the cost of such deputation shall be paid by the person at whose instance such erection or execution is being continued or to whom notice under sub-section (1) was given and shall be recoverable from such person as an arrear of tax under this Act.""", "procedure"),
sec(HMCA, "263", "Power of Commissioner to require alteration of work",
    """(1) The Commissioner may, at any time during the erection of any building or execution of any work or at any time within three months after the completion thereof, by a written notice specify any matter in respect of which such erection or execution is without or contrary to the sanction referred to in section 254 or is in contravention of any condition of such sanction or any of the provisions of this Act or any bye-laws made thereunder and require the person who gave the notice under section 251 or section 252 or the owner of such building or work either- (a) to make such alterations as may be specified in the said notice with the object of bringing the building or work in conformity with the said sanction, condition or provisions; or (b) to show cause why such alterations should not be made within the period stated in the notice. (2) If the person or the owner does not show cause as aforesaid, he shall be bound to make the alterations specified in the notice. (3) If the person or the owner shows cause as aforesaid, the Commissioner shall by an order either cancel the notice issued under sub-section (1) or confirm the same subject to such modifications as he thinks fit.""", fine=2000),
sec(HMCA, "263A(1)", "Power to seal premises",
    """The Commissioner may, at any time, before or after making an order under section 261 or 262 may order to seal the premises.""",
    notes="Inserted by Haryana Act 12 of 2013 (Haryana Govt. Gazette (Extra.) 26.09.2013)."),
sec(HMCA, "263A(2)", "Removal of seal - purposes",
    """Where any premises has been sealed, the Commissioner may order such seal to be removed for the purpose of- (a) allowing an opportunity to the owner to bring it in conformity with the sanctioned building plan as per the provisions of this Act, rules or bye-laws framed thereunder within a period, which shall not exceed three months; or (b) allowing the functionaries of the Corporation to bring it in conformity with the sanctioned building plan as per the provisions of this Act, rules or bye-laws framed thereunder at the cost of the owner; or (c) demolition, at the cost of the owner.""", "procedure"),
sec(HMCA, "263A(3)", "Prohibition on removal of seal",
    """No person shall remove such seal except- (a) under an order made by the Commissioner under sub-section (2); or (b) under an order of the appellate authority."""),
sec(HMCA, "263A(4)", "Appeal against sealing order",
    """Where any order of sealing has been passed under sub-section (1), the owner may file an appeal before the Divisional Commissioner concerned within a period of seven days of passing of such order. The Divisional Commissioner may either reject the appeal or stay the order to allow the owner to bring the premises in accordance with the sanctioned building plan as per the provisions of this Act, rules or the bye-laws framed thereunder, with such conditions including furnishing of a bank guarantee of an amount, as deemed fit. On failure of the owner to adhere to the conditions of the order, bank guarantee shall be revoked and the premises shall be liable for demolition, at the cost of the owner. Such cost shall be paid by the owner within a period of one month from the date of demolition of the said premises.""", "appeal"),
sec(HMCA, "263A(5)", "Recovery of demolition cost as arrears of land revenue",
    """In the event of non-payment of the cost by the owner as per sub-section (4), the same shall be recoverable as arrears of land revenue.""", "procedure", verify=True,
    notes="Gazette text reads 'as per sub-section (3)'; the cross-reference appears to be to sub-section (4)."),
sec(HMCA, "264", "Completion certificate and prohibition on occupation",
    """(1) Every person who employs a licensed architect or engineer or a person approved by the Commissioner to design or erect a building or execute any work shall, within one month after the completion of the erection of the building or execution of the work, deliver or send or cause to be delivered or sent to the Commissioner a notice in writing of such completion accompanied by a certificate in the form prescribed by bye-laws made in this behalf and shall give to the Commissioner all necessary facilities for the inspection of such building or work. (2) No person shall occupy or permit to be occupied any such building or use or permit to be used any building or a part thereof affected by any such work until permission has been granted by the Commissioner in this behalf in accordance with bye-laws made under this Act: Provided that if the Commissioner fails within a period of thirty days after the receipt of the notice of completion to communicate his refusal to grant such permission, it shall be deemed to have been granted.""", fine=500, daily_fine=50),
sec(HMCA, "265(1)", "Restrictions on use of buildings",
    """No person shall, without the written permission of the Commissioner, or otherwise than in conformity with the conditions, if any, of such permission- (a) use or permit to be used for human habitation any part of a building not originally erected or authorised to be used for that purpose or not used for that purpose before any alteration has been made therein by any work executed in accordance with the provisions of this Act and of the bye-laws made thereunder; (b) change or allow the change of the use of any land or building; (c) convert or allow the conversion of one kind of tenement into another kind.""", fine=1000, daily_fine=100),
sec(HMCA, "265(2)-(6)", "Removal of dangerous buildings",
    """(2) If it appears to the Commissioner at any time that any building is in a ruinous condition, or likely to fall, or in any way dangerous to any person occupying, resorting to or passing by such building or any other building or place in the neighbourhood of such building, the Commissioner may, by order in writing, require the owner or occupier of such building to demolish, secure or repair such building or do one or more of such things within such period as may be specified in the order, as to prevent all cause of danger therefrom. (3) The Commissioner may also, if he thinks fit, require such owner or occupier by the order made under sub-section (2) either forthwith or before proceeding to demolish, secure or repair the building to set up a proper and sufficient board or fence for the protection of passers-by and other persons, with a convenient platform and hand rail wherever practicable to serve as a footway for passengers outside of such board or fence. (4) If it appears to the Commissioner that danger from a building which is in ruinous condition or likely to fall is imminent, he may, before making the order aforesaid, fence off, demolish, secure or repair the said building or take such steps as may be necessary to prevent the danger. (5) If the owner or occupier of the building does not comply with the order within the period specified therein, the Commissioner shall take such steps in relation to the building as to prevent all cause of danger therefrom. (6) All expenses incurred by the Commissioner in relation to any building under this section shall be recoverable from the owner or occupier thereof as an arrear of tax under this Act.""", fine=2000, daily_fine=200),
sec(HMCA, "266", "Power to order building to be vacated in certain circumstances",
    """(1) The Commissioner may by order in writing direct that any building, which in his opinion is in a dangerous condition or is not provided with sufficient means of egress in case of fire or is occupied in contravention of section 264, be vacated forthwith or within such period as may be specified in the order: Provided that at the time of making such order the Commissioner shall record a brief statement of the reasons therefor. (2) If any person fails to vacate the building in pursuance of such order the Commissioner may direct any police officer to remove such person from the building and the police officer shall comply with such direction accordingly. (3) The Commissioner shall, on the application of any person who has vacated, or has been removed from any building in pursuance of an order made by him, allow such person to reoccupy the building on the expiry of the period for which the order has been in force; provided that the reasons on account of which the vacation was ordered have been rectified or have ceased to exist.""", fine=1000, daily_fine=100),
sec(HMCA, "284", "Power of Commissioner to order demolition of buildings unfit for human habitation",
    """(1) Notwithstanding anything contained in section 144 of the Code of Criminal Procedure, 1973, where the Commissioner upon any information in his possession is satisfied that any building is unfit for human habitation and is not capable at a reasonable expense of being rendered so fit, he shall serve upon the owner of the building and upon any other person having an interest in the building, whether as a lessee, mortgagee or otherwise a notice to show cause within such time as may be specified in the notice as to why an order of demolition of the building should not be made. (2) If any of the persons upon whom a notice has been served under sub-section (1), appears in pursuance thereof before the Commissioner and gives an undertaking to him that such person shall, within a period specified by the Commissioner, execute such works of improvement in relation to the building as will, in the opinion of the Commissioner render the building fit for human habitation or an undertaking that the building shall not be used for human habitation until the Commissioner, on being satisfied that it has been rendered fit for that purpose, cancels the undertaking, the Commissioner shall not make an order of demolition of the building. (3) If no such undertaking as is mentioned in sub-section (2) is given, or if in a case where any such undertaking has been given, any work of improvement to which the undertaking relates is not carried out within the specified period or the building is at any time used in contravention of the terms of the undertaking, the Commissioner shall forthwith make an order of demolition of the building requiring that the building shall be vacated within a period to be specified in the order not being less than thirty days from the date of the order, and that it shall be demolished within six weeks of the expiration of that period. (4) Where an order of demolition of a building under this section has been made, the owner of building or any other person having an interest therein shall demolish that building within the time specified in that behalf by the order, and if the building is not demolished within that time, the Commissioner shall demolish the building and sell the materials thereof. (5) Any expenses incurred by the Commissioner under sub-section (4), if not satisfied out of the proceeds of the sale of materials of the building, shall be recovered from the owner of the building or any other person having an interest therein as an arrear of tax under this Act.""", fine=2000, daily_fine=200),
sec(HMCA, "315", "Power to require buildings, wells etc. to be rendered safe",
    """Where any building, or wall, or anything affixed thereto, or any well, tank, reservoir, pool, depression or excavation, or any bank or tree, is in the opinion of the Commissioner, in a ruinous state for want of sufficient repairs, protection or enclosure, a nuisance or dangerous to persons passing by or dwelling or working in the neighbourhood, the Commissioner may by notice in writing require the owner or part-owner or person claiming to be the owner or part-owner thereof or failing any of them, the occupier thereof, to remove the same or may require him to repair, protect or enclose the same in such manner as he thinks necessary and if the danger is, in the opinion of the Commissioner, imminent, he shall forthwith take such steps as he thinks necessary to avert the same."""),
sec(HMCA, "346(1)", "Declaration of controlled area",
    """Notwithstanding any law for the time being in force, the Commissioner may, with the previous approval of the Government, by notification, declare the whole or any part of the area within the Corporation to be a controlled area provided that the same has not been declared as controlled area under the Punjab Scheduled Roads and Controlled Areas Restriction of Unregulated Development Act, 1963 (Act 41 of 1963)."""),
sec(HMCA, "380", "Punishment for certain offences (Third Schedule)",
    """Whoever- (a) contravenes any provision of any of the sections, sub-sections, clauses, provisos or other provisions of this Act mentioned in the first column of the table in the Third Schedule; or (b) fails to comply with any order lawfully given to him or any requisition lawfully made upon him under any of the said sections, sub-sections, clauses, provisos or other provisions shall be punishable- (i) with fine which may extend to the amount specified in the third column of the said Table; and (ii) in the case of a continuing contravention or failure, with an additional fine which may extend to the amount specified in the fourth column of that Table for every day during which such contravention or failure continues after conviction for the first such contravention or failure.""", "penalty"),
sec(HMCA, "381", "General penalty",
    """Whoever, in any case in which a penalty is not expressly provided by this Act, fails to comply with any notice, order or requisition issued under any provisions thereof, or otherwise contravenes any of the provisions of this Act, shall be punishable with fine which may extend to five hundred rupees, and in the case of a continuing failure or contravention with an additional fine which may extend to fifty rupees for every day after the first, during which he has persisted in the failure or contravention.""", "penalty", fine=500, daily_fine=50),
sec(HMCA, "382", "Offences by companies",
    """(1) Where an offence under this Act has been committed by a company, every person who, at the time the offence was committed, was in charge of and was responsible to the company for the conduct of the business of the company, as well as the company, shall be deemed to be guilty of the offence and shall be liable to be proceeded against and punished accordingly: Provided that nothing contained in this sub-section shall render any such person liable to any punishment provided in this Act, if he proves that the offence was committed without his knowledge or that he exercised all due diligence to prevent the commission of such offence. (2) Notwithstanding anything contained in sub-section (1) where an offence under this Act has been committed by a company and it is proved that the offence has been committed with the consent or connivance of, or is attributable to any neglect on the part of, any director, manager, secretary or other officer of the company, such director, manager, secretary or other officer shall also be deemed to be guilty of that offence and shall be liable to be proceeded against and punished accordingly.""", "penalty", verify=True),
sec(HMCA, "386", "Prosecution",
    """Save as otherwise provided in this Act, no court shall try an offence made punishable by or under this Act or any rule or any bye-law made thereunder, except on the complaint of, or upon information received from the Commissioner, or any other officer of the Corporation authorised by it in this behalf.""", "procedure"),
sec(HMCA, "387", "Composition of offences",
    """(1) The Commissioner or any other officer of the Corporation authorised by it in this behalf by a general or special order or a sub-committee of the Corporation appointed by it may, either before or after the institution of the proceedings, compound any offence made punishable by or under this Act or any rule or any bye-law made thereunder. (2) Where an offence has been compounded, the offender, if in custody, shall be discharged and no further proceedings shall be taken against him in respect of the offence so compounded.""", "procedure"),
sec(HMCA, "388", "Protection of action of the Corporation etc.",
    """No suit or prosecution shall be entertained in any court against the Corporation or against the Commissioner or against any Corporation Officer or other Corporation employee or against any person acting under the order or direction of the Corporation, the Commissioner or any Corporation officer or other Corporation employee, for anything which is in good faith done or intended to be done, under this Act or any rule, regulation or bye-law made thereunder.""", "procedure"),
sec(HMCA, "393", "Penalty for breaches of bye-laws",
    """(1) Any bye-law made under this Act may provide that a contravention thereof shall be punishable- (a) with fine which may extend to five hundred rupees; or (b) with fine which may extend to five hundred rupees and in the case of continuing contravention, with an additional fine which may extend to fifty rupees for every day during which such contravention continues after conviction for the first contravention; or (c) with fine which may extend to fifty rupees for every day during which the contravention continues, after the receipt of a notice from the Commissioner or any Corporation officer duly authorised in that behalf by the person contravening the bye-law requiring such person to discontinue such contravention. (2) Any such bye-law may also provide that a person contravening the same shall be required to remedy so far as lies in his power, the mischief, if any, caused by such contravention.""", "penalty"),
sec(HMCA, "401(2)", "Delegation by the Commissioner",
    """The Commissioner may, by order direct that any power exercisable or duty to be performed by him under this Act or any rule, regulation or bye-law made thereunder may be exercised or performed by a Corporation officer or other Corporation employee.""", "delegation", verify=True,
    notes="Basis on which the Joint Commissioner exercises the Commissioner's powers under ss.261, 262, 263 and 263A. The delegation order number must be quoted in every notice/order."),
sec(HMCA, "402", "Validity of notices and other documents",
    """No notice, order, requisition, licence, permission in writing or any other document issued under this Act, shall be invalid merely by reason of defect of form.""", "procedure"),
sec(HMCA, "403", "Admissibility of document or entry as evidence",
    """A copy of any receipt, application, plan, notice, order or other document or of any entry in a register in the possession of any Corporation authority shall, if duly certified by the legal keeper thereof or other person authorised by the Commissioner in this behalf, be admissible in evidence of the existence of the document or entry and shall be admitted as evidence of the matters and transactions therein recorded in every case where, and to the same extent to which, the original document or entry would if produced, have been admissible to prove such matters and transactions.""", "procedure",
    notes="Basis for treating the system's digitally signed notices, geotagged photographs and audit log as certified records."),
sec(HMCA, "405", "Prohibition against obstruction of Corporation authority etc.",
    """No person shall obstruct the Corporation or the Commissioner, the Mayor or any of the Deputy Mayors, any members or any person employed by the Corporation or any person with whom the Commissioner has entered into a contract on behalf of the Corporation, in the performance of their duty or of anything which they are empowered or required to do by virtue or in consequence of any provision of this Act or of any rule, regulation or bye-law made thereunder.""", "penalty", fine=500, verify=True),
sec(HMCA, "407", "Prohibition against removal or obliteration of notice",
    """No person shall, without authority in that behalf remove, destroy, deface or otherwise obliterate any notice exhibited by or under orders of the Corporation or any other Corporation authority or any Corporation Officer or other Corporation employee specified by the Commissioner in this behalf.""", "penalty", fine=500),
sec(HMCA, "408", "Prohibition against unauthorised removal, deposit, encroachment on Corporation land",
    """No person shall, without authority in that behalf, remove earth, sand or other material or deposit any matter or make any encroachment in or on any land vested in the Corporation or in any way obstruct the same.""", fine=500),
sec(HMCA, "408A(1)", "Power to evict persons from Corporation premises/land - show cause notice",
    """If the competent authority is satisfied- (a) that any person authorised to occupy any premises of the Corporation has- (i) not paid rent lawfully due from him in respect of such premises for a period of more than two months; or (ii) sublet, without the permission of the Commissioner or any other officer duly empowered to grant such permission, the whole or any part of such premises; or (iii) otherwise acted in contravention of any of the terms expressed or implied, under which he is authorised to occupy such premises; or (b) that any person is in unauthorised occupation of any premises/land or building/structure constructed thereon, of the Corporation, the competent authority may, notwithstanding anything contained in any law for the time being in force, by notice served upon him by post or by person and if such person avoids service or is not available for service of notice or refuses to accept notice, then by affixing a copy of it on the outer door or some other conspicuous part of such premises/land or building or by beating of drums or in such manner, as may be prescribed, call upon such person to appear and show cause why he should not be ordered to vacate the said premises/land or building/structure constructed thereon or demolish unauthorised construction and to restore to its original state or to bring it in conformity with the provisions of this Act or rules framed thereunder, as the case may be, within a period of seven days from the date of service of the notice.""",
    notes="Inserted by amendment (footnote 30 in the bare act). 'Competent authority' = Joint Commissioner, s.2(4A)."),
sec(HMCA, "408A(2)", "Order to vacate / demolish / restore",
    """If such person fails to show cause to the satisfaction of the competent authority or fails to appear or refuses to appear before the competent authority, as the case may be, within a period of seven days, the competent authority shall pass an order requiring him to vacate such premises/land or building/structure constructed thereon or demolish unauthorised construction and restore to its original state or to bring it in conformity with the provisions of this Act or the rules framed thereunder, as the case may be, within a further period of seven days.""", "procedure"),
sec(HMCA, "408A(3)", "Eviction / demolition by the competent authority and recovery of cost",
    """If the order made under sub-section (2) is not carried out or complied with within the specified period, the competent authority at the expiry of the period so specified, shall evict that person from, and take possession of, the premises/land or building/structure constructed thereon or demolish unauthorised construction or restore to its original state or bring it in conformity with the provisions of this Act or the rules framed thereunder, as the case may be, and shall for that purpose use such force, as may be necessary and the cost incurred on such measures shall, if not paid on demand being made to him, be recoverable from such persons as arrears of land revenue.""", "procedure"),
sec(HMCA, "408A(4)", "Immediate action where contravention continues",
    """Even before the expiry of a further period of seven days mentioned under sub-section (2), if the competent authority is satisfied that instead of vacation of premises/land or building/structure constructed thereon or demolition of unauthorised construction, as the case may be, the person continues with the contravention, the competent authority shall himself take such measures and use such force as may appear necessary to give effect to the order under sub-section (2) and the cost of such measures shall if not paid on demand being made to him, be recoverable from such person as arrears of land revenue.""", "procedure"),
sec(HMCA, "408B", "Appeal against order under s.408A",
    """(1) Any person aggrieved by an order of the competent authority under sub-section (2) of section 408A may, within a period of seven days from the date of the order under sub-section (2) of section 408A, prefer an appeal to the Commissioner. (2) Where an appeal is preferred under sub-section (1), the Commissioner may stay the enforcement of the order of the competent authority for such period and on such conditions, as it deems fit. (3) Every appeal under this section shall be disposed of by the Commissioner within a period of sixty days.""", "appeal"),
sec(HMCA, "408C", "Finality of order",
    """Save as otherwise expressly provided in this Act, every order made by the competent authority under section 408A or by the Commissioner under section 408B shall be final and shall not be called in question in any original suit, application or execution proceedings and no injunction shall be granted by any court or other authority in respect of any action taken or to be taken in pursuance of any power conferred by or under sections 408A and 408B of this Act.""", "appeal"),
sec(HMCA, "Third Schedule", "Table of fines referred to in section 380 (building and street provisions)",
    """Section 235 - projection upon streets: fine as per Schedule; Section 236(2) - failure to remove verandah/balcony: Rs 500 + Rs 50/day; Section 237: Rs 1,000 + Rs 50/day; Section 238(1) - erection of structure/fixture obstructing streets: Rs 1,000 + Rs 100/day; Section 238(2) - deposit of things in streets: Rs 500; Section 243(1) - opening streets / depositing building material without permission: Rs 500 + Rs 50/day; Section 246(1): Rs 500 + Rs 50/day; Section 250 - erection of building without sanction of the Commissioner: Rs 5,000 + Rs 500/day; Section 251(1) - failure to give notice of intention to erect: Rs 500; Section 252 - failure to give notice for additions: Rs 500 + Rs 50/day; Section 255(4) - commencement of work without notice: Rs 2,000 + Rs 200/day; Section 257: Rs 500 + Rs 50/day; Section 258(1): Rs 1,000 + Rs 50/day; Section 258(2) - erection within regular line of street or in contravention of scheme/plan: Rs 1,000; Section 260 - inflammable material: Rs 1,000; Section 261 - failure to demolish buildings erected without sanction or erection in contravention of order: Rs 2,000 + Rs 200/day; Section 262 - erection in contravention of conditions of sanction etc.: Rs 2,000 + Rs 200/day; Section 263 - failure to carry out alterations: Rs 2,000; Section 264(1)-(2) - completion certificate / occupation: Rs 500 + Rs 50/day; Section 265(1) - restrictions on user: Rs 1,000 + Rs 100/day; Section 265(2)-(3) - ruinous structures: Rs 2,000 + Rs 200/day; Section 266(1) - failure to vacate dangerous building: Rs 1,000 + Rs 100/day; Section 284 - demolition of building unfit for habitation: Rs 2,000 + Rs 200/day; Section 407 - removal/defacing of notice: Rs 500; Section 408 - encroachment on land vested in the Corporation: Rs 500.""", "schedule"),
]

# ---- Haryana Building Code, 2017 --------------------------------------------
sections += [
sec(HBC, "1.2(xxv)", "Definition - 'Competent Authority'",
    """"Competent Authority" shall mean an officer/agency duly authorized;""", "definition",
    notes="Within municipal limits the Commissioner, Municipal Corporation (and officers delegated by him) is the Competent Authority for building plan sanction under the HMC Act 1994."),
sec(HBC, "2.1(1)", "Application for erection or re-erection of building",
    """Any person who intends to erect, re-erect or make alteration in any place in a building or demolish any building shall give notice in writing to the Competent Authority of his/her intention in the Form BR-I, accompanied by the documents specified (ownership documents, plans, structural drawings, certificates of the Architect/Engineer, etc.).""", "procedure"),
sec(HBC, "2.1(2)", "Duty of Architect/Engineer to report violations",
    """Every person applying under Code 2.1(1) shall appoint an Architect/Engineer for drawing up of building plans/structural drawings and for the supervision of erection or re-erection of the building. ... During construction if appointed Architect/Engineer notices that violation (except compoundable) are going on he shall intimate the owner and advise him to stop further construction and remove the violation, will also intimate to the concerned authority."""),
sec(HBC, "2.2(3)", "Self-certification - right to check and rectification of violations",
    """Competent Authority or any other person authorized by him reserves the right to check the building plans and construction at any stage and violations (except compoundable ones), if found shall have to be rectified by the owner/applicant. In case the owner/applicant fail to rectify violations, the Competent Authority may take necessary steps to remove the violations. Action shall also be taken against the defaulting Architect by referring his case to the Council of Architecture for misconduct and debarring/blacklisting the Architect from doing practice in State Government Departments/Authorities. All rectifications shall be at the risk and cost of the owner and no plea of the owner shall be entertained for any default committed by the Architect engaged by him. In all such cases the procedure of self-certification shall stand aborted."""),
sec(HBC, "2.2(4)", "Notice to alter or demolish building erected in contravention",
    """If a building is erected or re-erected or construction work is commenced in contravention to any of the building regulations, the Competent Authority or any other person authorized by him shall be competent to require the building to be altered or demolished, by a written notice delivered to the owner. Such notice shall also specify the period during which such alteration or demolition has to be completed and if the notice is not complied with, the Competent Authority or any other person authorized by him may demolish the said building at the expense of the owner."""),
sec(HBC, "4.3-4.4", "Validity and re-validation of sanctioned plans",
    """The sanction of building plans remains valid for the period specified in the Code (two years, extendable by re-validation on payment of the prescribed fee); construction continued after expiry of validity without re-validation is construction without a valid sanction.""", "substantive", verify=True,
    notes="Summary. Verbatim validity periods to be confirmed from Codes 4.3 and 4.4 of the current HBC."),
sec(HBC, "4.5", "Deemed sanction",
    """The Competent Authority shall pass an order within a period of twenty days of submission of building plans, accompanied by all necessary documents as mentioned in Code 2.1, either sanctioning or rejecting it. The building plan shall be deemed to be sanctioned, if it is in conformity with building Code and in accordance with the permitted land use of the area and all leviable fee/charges have been deposited by the applicant but no orders have been passed by the Competent Authority within the specified time.""", "procedure"),
sec(HBC, "4.6", "Submission of revised building plans during the validity period of sanction",
    """(1) If during the construction of a building, any deviation from the sanctioned plan is intended to be made, approval of the Competent Authority for the same may be obtained before the change is made. The revised plan showing the deviations shall be submitted and the procedure laid down for the sanction of building plan as stated in Code No. 2.1 and 2.2, shall be followed for all revised plans, along with the depositing balance scrutiny fee, if any. (2) Any notice and building approval is not necessary for compoundable alterations/violations, which do not otherwise violate any provisions regarding general building requirements, structural stability and fire safety requirements of this building Code."""),
sec(HBC, "4.7", "Revocation of sanction",
    """The sanction granted under Code 4.2 can be revoked by the Competent Authority, if it is found that such sanction has been obtained by the owner by misrepresentation of material facts or fraudulent document submitted along with the building plan application or otherwise or the construction is not being done in accordance with the sanction granted."""),
sec(HBC, "4.9", "Damp Proof Course (DPC) certificate",
    """The owner (or the Architect, in case of self certification) shall submit a certificate that the construction of building up to DPC level is in accordance with the sanctioned plan before proceeding further.""", "procedure", verify=True),
sec(HBC, "4.10(2)", "Occupation Certificate mandatory before occupation",
    """No owner/applicant shall occupy or allow any other person to occupy new building or part of a new building or any portion whatsoever, until such building or part thereof has been certified by the Competent Authority or by any officer authorized by him in this behalf as having been completed in accordance with the permission granted and an 'Occupation Certificate' has been issued in Form BR-VII. However, Competent Authority may also seek composition charges of compoundable violations which are compoundable before issuance of Form BR-VII. Further, the water, sewer and electricity connection be released only after issuance of said occupation certificate by the Competent Authority."""),
sec(HBC, "4.11(2)", "Self-certified occupation - non-compoundable violations",
    """Provided, if any violation found within time prescribed above during inspection, which is not listed in compoundable violations stated at Code 4.11(1)(i), then the violation be compounded (or demolished if it is non-compoundable), as per composition charges prescribed by the Competent Authority."""),
sec(HBC, "4.12", "Revocation of Occupation certificate",
    """In case, after the issuance of occupation certificate, if found at any stage that the building is used for some other purpose against the permission or make any addition/alteration in the building then, after affording personal hearing to the owner, the Competent Authority may pass orders for revocation of occupation permission and the same shall be restored only after removal of violations."""),
sec(HBC, "6.2(1)-(2)", "Sub-division and amalgamation of plots",
    """(1) Division of plot into smaller units is permissible in core areas with the prior approval of the Competent Authority. Each such plot shall be accessible separately and independently through a public road laid out and constructed to the satisfaction of the Competent Authority. (2) Except as otherwise expressly provided at the time of sale of a plot, not more than one building unit shall be erected on any one plot, but two or more plots may be amalgamated for purpose of erection of one "building unit". In case of back to back plots which are to be amalgamated, two building units may be allowed maintaining the rear setbacks intact subject to the condition that a maximum of four dwelling units shall be permissible on the amalgamated plot."""),
sec(HBC, "6.3", "Proportion of the site which may be covered with buildings (ground coverage, FAR, height, setbacks)",
    """The proportions of covered area of a building, including ancillary buildings, shall be in accordance with the plot categories given in the sub-Codes and the remaining portion shall be left open in the form of open space around the building. ... The stilts are permitted for parking purposes in residential and commercial plots of all sizes, subject to the condition that maximum permissible height of building shall not exceed 15 metres. ... Any violation of the permissible ground coverage limit as indicated in the table shall be non-compoundable.""",
    notes="Permissible ground coverage, FAR, height and setback tables are in Code 6.3 (residential plotted), 6.4 (architectural control) and the use-specific chapters. The inspection form captures measured vs permitted values."),
sec(HBC, "7.1", "Parking", """Parking shall be provided as per the norms of the Code; stilt/basement parking areas shall be used only for parking.""", "substantive", verify=True),
sec(HBC, "7.16", "Basement", """Basement construction is permitted only as per the Code (extent, use, setbacks, structural safety and drainage conditions).""", "substantive", verify=True),
sec(HBC, "7.17", "Fire safety", """Fire safety requirements (means of egress, fire NOC for buildings above the prescribed height) as per the Code and the Haryana Fire and Emergency Services Act.""", "substantive", verify=True),
]

# ---- Haryana Public Premises and Land (Eviction and Rent Recovery) Act, 1972 --
sections += [
sec(HPPA, "2(c)", "Definition - 'premises'",
    """"premises" means any land, whether used for agricultural or non-agricultural purposes, or any building or part of a building and includes,- (i) the garden, grounds and out-houses, if any, appertaining to such building or part of a building; and (ii) any fittings affixed to such building or part of a building for the more beneficial enjoyment thereof;""", "definition"),
sec(HPPA, "2(e)", "Definition - 'public premises'",
    """"public premises" means any premises belonging to, or taken on lease or requisitioned by, or on behalf of, the State Government, or requisitioned by the competent authority under the Punjab Requisitioning and Acquisition of Immovable Property Act, 1953, and includes any premises belonging to any local authority, or District Soldiers, Sailors and Airmen's Board or any university established by law or any Corporation or Board owned or controlled by the State Government;""", "definition",
    notes="'Local authority' includes the Municipal Corporation; hence municipal land is also 'public premises' and the Collector's HPPA route is available in addition to s.408A HMC Act."),
sec(HPPA, "3", "Unauthorised occupation of public premises",
    """For the purposes of this Act, a person shall be deemed to be in unauthorised occupation of any public premises- (a) where he has, whether before or after the commencement of this Act, entered into possession thereof otherwise than under and in pursuance of any allotment, lease or grant; or (b) where he, being an allottee, lessee or grantee, has, by reason of the determination or cancellation of his allotment, lease or grant in accordance with the terms in that behalf therein contained, ceased, whether before or after the commencement of this Act, to be entitled to occupy or hold such public premises; or (c) where any person authorised to occupy any public premises has, whether before or after the commencement of this Act,- (i) sub-let, in contravention of the terms of allotment, lease or grant, without the permission of the State Government or of any other authority competent to permit such sub-letting, the whole or any part of such public premises, or (ii) otherwise acted in contravention of any of the terms, express or implied, under which he is authorised to occupy such public premises. Explanation.- For the purposes of clause (a), a person shall not merely by reason of the fact that he has paid any rent be deemed to have entered into possession as allottee, lessee or grantee."""),
sec(HPPA, "4", "Issue of notice to show cause against order of eviction",
    """(1) If the Collector is of opinion that any persons are in unauthorised occupation of any public premises situate within his jurisdiction and that they should be evicted, the Collector shall issue, in the manner hereinafter provided, a notice in writing calling upon all persons concerned to show cause why an order of eviction should not be made. (2) The notice shall- (a) specify the grounds on which the order of eviction is proposed to be made; and (b) require all persons concerned, that is to say, all persons who are, or may be, in occupation of, or claim interest in, the public premises, to show cause, if any, against the proposed order on or before such date as is specified in the notice, being a date not earlier than ten days from the date of issue thereof. (3) The Collector shall cause the notice to be affixed on the outer door or some other conspicuous part of the public premises, or of the estate in which the public premises are situate, and in such other manner as may be prescribed, whereupon the notice shall be deemed to have been duly given to all persons concerned. (4) Where the Collector knows or has reasons to believe that any persons are in occupation of the public premises, then without prejudice to the provisions of sub-section (3), he shall cause a copy of the notice to be served on every such person by post or by delivering or tendering it to that person or in such other manner as may be prescribed.""", "procedure"),
sec(HPPA, "5", "Eviction of unauthorised persons",
    """(1) If, after considering the cause, if any, shown by any person in pursuance of a notice under section 4 and any evidence he may produce in support of the same and after giving him a reasonable opportunity of being heard, the Collector is satisfied that the public premises are in unauthorised occupation, the Collector may make an order of eviction, for reasons to be recorded therein, directing that the public premises shall be vacated, on such date as may be specified in the order, by all persons who may be in occupation thereof or any part thereof, and cause a copy of the order to be affixed on the outer door or some other conspicuous part of the public premises or of the estate in which the public premises are situate. (2) If any person refuses or fails to comply with the order of eviction within thirty days of the date of its publication under sub-section (1), the Collector or any other officer duly authorised by him in this behalf may evict that person from, and take possession of, the public premises and may, for that purpose, use such force as may be necessary.""", "procedure"),
sec(HPPA, "6(1)", "Disposal of property left on public premises by unauthorised occupants",
    """Where any persons have been evicted from any public premises under section 5, the Collector may, after giving fourteen days notice to the persons from whom possession of the public premises has been taken and after publishing the notice in at least one newspaper having circulation in the locality, remove or cause to be removed or sell by public auction any property remaining on such premises.""", "procedure"),
sec(HPPA, "7(2)-(3)", "Power to recover damages for unauthorised occupation",
    """(2) Where any person is, or has at any time been, in unauthorised occupation of any public premises, the Collector may, having regard to such principles of assessment of damages as may be prescribed, assess the damages on account of the use and occupation of such premises and may, by order, require that person to pay the damages within such time and in such instalments as may be specified in the order. (3) No order under sub-section (1) or sub-section (2) shall be made against any person until after the issue of a notice in writing to the person calling upon him to show cause within such time as may be specified in the notice, why such order should not be made, and until his objections, if any, and any evidence he may produce in support of the same, have been considered by the Collector.""", "procedure"),
sec(HPPA, "9", "Appeals",
    """(1) An appeal shall lie from every order of the Collector made in respect of any public premises under section 5 or section 7 to the Commissioner. (2) An appeal under sub-section (1) shall be preferred,- (a) in the case of an appeal from an order under section 5, within thirty days from the date of publication of the order under sub-section (1) of that section; and (b) in the case of an appeal from an order under section 7, within thirty days from the date on which the order is communicated to the appellant: Provided that the Commissioner may entertain the appeal after the expiry of the said period of thirty days if he is satisfied that the appellant was prevented by sufficient cause from filing the appeal in time. (3) Where an appeal is preferred from an order of the Collector, the Commissioner may stay the enforcement of that order for such period and on such conditions as he deems fit. (4) Every appeal under this section shall be disposed of by the Commissioner as expeditiously as possible. (5) The costs of any appeal under this section shall be in the discretion of the Commissioner.""", "appeal",
    notes="'Commissioner' here is the Divisional Commissioner (s.2 read with the Punjab Land Revenue Act)."),
sec(HPPA, "10", "Finality of orders",
    """Save as otherwise expressly provided in this Act, every order made by the Collector or Commissioner under this Act shall be final and shall not be called in question in any original suit, application or execution proceeding and no injunction shall be granted by any court or other authority in respect of any action taken or to be taken in pursuance of any power conferred by or under this Act.""", "appeal"),
sec(HPPA, "11(1)", "Offence of re-occupation after eviction",
    """If any person who has been evicted from any public premises under this Act again occupies the premises without authority for such occupation he shall be punishable with imprisonment for a term which may extend to one year, or with fine which may extend to one thousand rupees, or with both.""", "penalty", verify=True),
sec(HPPA, "14", "Recovery of rent, damages and costs as arrears of land revenue",
    """If any person refuses or fails to pay the arrears of rent payable under sub-section (1) of section 7 or the damages payable under sub-section (2) of that section or the costs awarded to the State Government or the local authority under sub-section (5) of section 9 or any portion of such rent, damages or costs, within the time, if any, specified therefor in the order relating thereto, the Collector shall proceed to recover the amount due as arrears of land revenue.""", "procedure"),
sec(HPPA, "15", "Bar of jurisdiction of civil courts",
    """No court shall have jurisdiction to entertain any suit or proceeding in respect of the eviction of any person who is in unauthorised occupation of any public premises or the recovery of the arrears of rent payable under sub-section (1) of section 7 or the damages payable under sub-section (2) of that section or the costs awarded to the State Government or the local authority under sub-section (5) of section 9 or any portion of such rent, damages or costs.""", "appeal"),
]

# ---- Punjab Scheduled Roads and Controlled Areas Restriction of Unregulated Development Act, 1963 ----
sections += [
sec(PSRCA, "3", "Restriction on erection of buildings along scheduled roads",
    """No person shall erect or re-erect any building or make or extend any excavation or lay out any means of access to a road within the restricted belt along a scheduled road except with the permission of the Director, Town and Country Planning.""", "substantive", verify=True, notes="Summary."),
sec(PSRCA, "7", "Restriction on use of land in controlled areas",
    """No person shall, in a controlled area, erect or re-erect any building, make or extend any excavation, lay out any means of access to a road, or use land for any purpose other than the one for which it was used on the date of publication of the notification, except with the permission (Change of Land Use) of the Director.""", "substantive", verify=True, notes="Summary."),
sec(PSRCA, "12(1)", "Offences and penalties",
    """Any person who erects or re-erects any building or makes or extends any excavation or lays out any means of access to a road in contravention of sections 3 or 6 or of any conditions imposed by an order under sections 8 or 10, or uses any land in contravention of section 7 or 10, shall be punishable with imprisonment of either description for a term which may extend to three years and shall also be liable to fine which may extend to fifty thousand rupees but shall not be less than ten thousand rupees, and in the case of a continuing contravention, with a further fine which may extend to one thousand rupees for every day during which the contravention continues after conviction for the first such contravention.""", "penalty", verify=True, notes="Summary of the amended provision (amended up to 2018)."),
sec(PSRCA, "12(2)-(3)", "Restoration / demolition by the Director",
    """(2) The Director may issue a notice calling upon the person to stop the construction/use and to appear and show cause within seven days why the land/building should not be restored to its original state; on failure the Director may pass an order of restoration (demolition). (3) If the order is not complied with within seven days, the Director may himself take the measures (including demolition) and recover the cost as arrears of land revenue; where the contravention continues during the show-cause period the Director may act at once.""", "procedure", verify=True, notes="Summary."),
sec(PSRCA, "12A", "Duty of police officers", """It shall be the duty of every police officer to communicate information regarding the design or commission of offences under the Act to the Director and to assist the Director and officers authorised by him in the lawful exercise of their powers.""", "procedure", verify=True, notes="Summary."),
]

# ---- Bharatiya Nyaya Sanhita, 2023 (criminal law references used in notices) ----
sections += [
sec(BNS, "223", "Disobedience to order duly promulgated by public servant",
    """Whoever, knowing that, by an order promulgated by a public servant lawfully empowered to promulgate such order, he is directed to abstain from a certain act, or to take certain order with certain property in his possession or under his management, disobeys such direction, shall, if such disobedience causes or tends to cause obstruction, annoyance or injury, or risk of obstruction, annoyance or injury, to any person lawfully employed, be punished with simple imprisonment for a term which may extend to six months, or with fine which may extend to two thousand five hundred rupees, or with both.""", "penalty", verify=True,
    notes="Successor to IPC s.188. Quoted in stop-work / sealing orders as the consequence of disobedience."),
sec(BNS, "221", "Obstructing public servant in discharge of public functions",
    """Whoever voluntarily obstructs any public servant in the discharge of his public functions, shall be punished with imprisonment of either description for a term which may extend to three months, or with fine which may extend to two thousand five hundred rupees, or with both.""", "penalty", verify=True, notes="Successor to IPC s.186."),
]

# ---- cross-referenced HMC Act / HBC provisions (headings + short text) ------
sections += [
sec(HMCA, "216", "Vesting of public streets in Corporation", """(1) All streets within the Municipal area which are or at any time have become public streets, and the pavements, stones and other materials thereof, shall vest in the Corporation. (2) All public streets vesting in the Corporation shall be under the control of the Commissioner and shall be maintained, controlled and regulated by him in accordance with the bye-laws made in this behalf."""),
sec(HMCA, "230", "Owner's obligation when dealing with land as building sites", """Every person who intends to sell, lease or otherwise dispose of land as building sites, or to lay out private streets, shall obtain sanction of the layout plan from the Commissioner before doing so.""", "substantive", verify=True, notes="Summary."),
sec(HMCA, "231", "Sanction of layout / private streets", """Layout plans of land intended to be used as building sites and private streets require sanction of the Commissioner under this section.""", "substantive", verify=True, notes="Summary."),
sec(HMCA, "232", "Alteration or demolition of street made in breach of section 231", """The Commissioner may by notice require the alteration or demolition of any private street laid out in breach of section 231 and, on non-compliance, may himself alter or demolish it and recover the expenses.""", "procedure", verify=True, notes="Summary."),
sec(HMCA, "252(1)(e)", "Works within regular line of street", """To repair, remove, construct, reconstruct, or make any addition to or structural alteration in any portion of a building abutting on a street which stands within the regular line of such street - requires sanction under section 252."""),
sec(HMCA, "254(2)(d)", "Ground of refusal - layout not sanctioned", """That in cases falling under section 230, lay out plans have not been sanctioned in accordance with section 231."""),
sec(HMCA, "254(2)(e)", "Ground of refusal - encroachment on Government / Corporation land", """That the building or work would be an encroachment on Government land or land vested in the Corporation."""),
sec(HMCA, "254(2)(g)", "Ground of refusal - contravention of building scheme", """That the building or work would be in contravention of any scheme sanctioned under section 267."""),
sec(HMCA, "255(2)", "Obligation to build in accordance with sanction", """Where a building or work is sanctioned or is deemed to have been sanctioned by the Commissioner under sub-section (1), the person who has given the notice shall be bound to erect the building or execute the work in accordance with such sanction but not so as to contravene any of the provisions of this Act or any other law or of any bye-law made thereunder."""),
sec(HMCA, "255(3)", "Fresh sanction if work not commenced within one year", """If the person or any one lawfully claiming under him does not commence the erection of the building or the execution of the work within one year of the date on which the building or work is sanctioned or is deemed to have been sanctioned, he shall have to give notice under section 252 or, as the case may be, under section 251 for fresh sanction."""),
sec(HMCA, "255(4)", "Notice of commencement", """Before commencing the erection of a building or execution of a work within the period specified in sub-section (3), the person concerned shall give notice to the Commissioner of the proposed date of the commencement of the erection of the building or the execution of the work.""", fine=2000, daily_fine=200),
sec(HMCA, "267", "Building Scheme", """The Corporation may, and if so required by the Government shall, draw up a building scheme for built areas and a town planning scheme for unbuilt areas, which may provide for the restriction of the erection or re-erection of buildings, building lines, and the use to which buildings may be put.""", "substantive", verify=True, notes="Summary."),
sec(HMCA, "282", "Power of Commissioner to require improvement of building unfit for human habitation", """(1) Where the Commissioner upon information in his possession is satisfied that any building is in any respect unfit for human habitation, he may, unless in his opinion the building is not capable at a reasonable expense of being rendered fit, serve upon the owner of the building a notice requiring him within such time not being less than thirty days as may be specified in the notice to execute the works of improvement specified therein and stating that in his opinion those works will render the building fit for human habitation.""", fine=1000),
sec(HBC, "3.5", "Constructing building as per Architectural Control Sheet", """Where an Architectural Control Sheet / zoning plan has been approved for a site, the building shall be constructed in conformity with it.""", "substantive", verify=True, notes="Summary."),
sec(HBC, "6.1", "Use of site, type and character of building", """No site shall be used for a purpose other than that for which it is designated in the Development Plan / zoning plan; the type and character of the building shall conform to the permitted land use.""", "substantive", verify=True, notes="Summary."),
sec(HBC, "6.4", "Architectural / Frame Control and siting of building", """Siting of buildings and frame control as per the approved zoning / architectural control of the area.""", "substantive", verify=True, notes="Summary."),
sec(HBC, "7.12", "Cantilevered roof and chajja projections", """Chajjas and cantilevered projections are permitted only to the extent specified in the Code and shall not project over public land beyond the permitted limits.""", "substantive", verify=True, notes="Summary."),
sec(HBC, "7.13", "Mezzanine floor", """Mezzanine floors are permitted only as per the area and height limits of the Code and are counted towards FAR as specified.""", "substantive", verify=True, notes="Summary."),
]

statutes = [
    {"code": HMCA, "title": "Haryana Municipal Corporation Act, 1994", "citation": "Haryana Act No. 16 of 1994 (as amended, incl. Act 1 of 2007 and Act 12 of 2013)", "jurisdiction": "Municipal Corporation of Gurugram", "primary": True},
    {"code": HBC, "title": "Haryana Building Code, 2017", "citation": "Notification No. Misc-138A-Loose/7/5/2006-2TCP dated 29.03.2017, with amendments up to 25.05.2023", "jurisdiction": "Whole of Haryana (building plan sanction, deviations, OC)", "primary": True},
    {"code": HPPA, "title": "Haryana Public Premises and Land (Eviction and Rent Recovery) Act, 1972", "citation": "Haryana Act No. 24 of 1972", "jurisdiction": "Government / local-authority land (Collector route)", "primary": True},
    {"code": PSRCA, "title": "Punjab Scheduled Roads and Controlled Areas Restriction of Unregulated Development Act, 1963", "citation": "Punjab Act 41 of 1963 (as applicable to Haryana)", "jurisdiction": "Controlled areas / scheduled roads (DTCP route)", "primary": False},
    {"code": BNS, "title": "Bharatiya Nyaya Sanhita, 2023", "citation": "Act 45 of 2023", "jurisdiction": "Criminal consequences quoted in orders", "primary": False},
]

# ----------------------------------------------------------------------------
# 2. VIOLATION CATALOGUE
# ----------------------------------------------------------------------------
# action_path codes drive the workflow engine (see backend/building_violations/services/workflow.py)
#   HMCA_261      : SCN (reasonable opportunity) -> demolition order u/s 261(1) (>=3 days) [+ stop-work 262 / sealing 263A]
#   HMCA_263      : alteration notice u/s 263 -> confirm/cancel -> if not complied, 261
#   HMCA_408A     : 7-day SCN by competent authority (JC) -> 7-day order -> eviction/demolition; appeal 408B (7 days)
#   HPPA_4_5      : Collector's SCN (>=10 days) -> eviction order s.5 -> 30 days -> force (co-ordinated with DC office)
#   HMCA_235_238  : notice to remove projection/encroachment (235(2)); summary removal 240 / 243(3)
#   HMCA_265_2    : dangerous building order (repair/secure/demolish)
#   HMCA_284      : unfit-for-habitation SCN -> undertaking / demolition order (30 days vacate + 6 weeks)
#   HMCA_266      : vacate order
#   HMCA_265_1    : misuse / change of use notice -> 265(1), HBC 4.12 (revoke OC)
GL, PL, DEV, ST, MIS, DAN, PROC = ("GOVT_LAND", "PRIVATE_LAND_NO_SANCTION", "DEVIATION_FROM_SANCTION", "STREET_ENCROACHMENT", "MISUSE_CHANGE_OF_USE", "DANGEROUS_UNFIT", "PROCEDURAL_NON_COMPLIANCE")

def v(code, cat, en, hi, desc, basis, contravenes, action_path, orders, scn_days, order_days, sev, compoundable, evidence, fine=None, daily=None, notes=None, appeal=None):
    return {
        "code": code,
        "category": cat,
        "title_en": en,
        "title_hi": hi,
        "description": " ".join(desc.split()),
        "legal_basis": basis,              # list of {statute, section}
        "contravention_of": contravenes,   # short human string used on the notice
        "action_path": action_path,
        "orders_available": orders,        # list of order types the JC may issue
        "scn_response_days_default": scn_days,
        "order_compliance_days_default": order_days,
        "statutory_minimum_days": {"HMCA_261": 3, "HMCA_408A": 7, "HPPA_4_5": 10, "HMCA_284": 30}.get(action_path, 0),
        "severity": sev,                   # CRITICAL | HIGH | MEDIUM | LOW
        "compoundable": compoundable,      # NO | YES | CONDITIONAL
        "evidence_checklist": evidence,
        "schedule_fine_inr": fine,
        "schedule_daily_fine_inr": daily,
        "appeal": appeal or {"HMCA_261": "Divisional Commissioner, within the period specified in the order (s.261(2)); sealing: 7 days (s.263A(4))",
                             "HMCA_408A": "Commissioner, within 7 days of the order (s.408B)",
                             "HPPA_4_5": "Appeal under s.9 HPPA 1972",
                             "HMCA_263": "Show cause under s.263(1)(b); order under s.263(3); thereafter s.261 remedies",
                             "HMCA_235_238": "Notice under s.235(2); summary removal u/s 240/243(3)",
                             "HMCA_265_2": "Order under s.265(2); Commissioner may act forthwith if danger imminent (s.265(4))",
                             "HMCA_284": "Show cause u/s 284(1); undertaking u/s 284(2)",
                             "HMCA_266": "Order u/s 266(1) with reasons; police removal u/s 266(2)",
                             "HMCA_265_1": "Notice u/s 265(1); revocation of OC after personal hearing (HBC 4.12)"}.get(action_path, ""),
        "notes": notes,
        "active": True,
    }

COMMON_EVIDENCE = ["Geotagged photographs of the structure from the street (front, both sides)", "Geotagged close-up of the violating portion", "Short video walk-through (max 60 s)", "Site plan / sketch with measurements", "PID or address, owner/occupier name and mobile", "Name of person supervising construction on site"]
GOVT_EVIDENCE = COMMON_EVIDENCE + ["Screenshot of the government-land layer showing the point inside the parcel", "Khasra/parcel number from the land record layer", "Photograph of any boundary pillars / demarcation"]
DEV_EVIDENCE = COMMON_EVIDENCE + ["Sanctioned plan number, date and licence/BR-I reference", "Measured vs permitted values (coverage, FAR, setbacks, height)", "DPC certificate / stage-completion records if any"]

violations = [
# --- A. Government / Corporation land ---------------------------------------
v("GL-01", GL, "Unauthorised construction / occupation on land vested in the Municipal Corporation",
  "नगर निगम में निहित भूमि पर अनधिकृत निर्माण / कब्ज़ा",
  """Any building, boundary wall, shed, hut, platform or structure raised on land vested in the Corporation (parks, green belts, community sites, road land, drain land, municipal plots, village common land vested after inclusion) without allotment, lease or permission.""",
  [{"statute": HMCA, "section": "408"}, {"statute": HMCA, "section": "408A(1)"}, {"statute": HMCA, "section": "408A(2)"}, {"statute": HMCA, "section": "408A(3)"}, {"statute": HMCA, "section": "408A(4)"}, {"statute": HMCA, "section": "254(2)(e)"}, {"statute": HMCA, "section": "250"}],
  "Sections 408 and 408A of the Haryana Municipal Corporation Act, 1994 (unauthorised occupation of / encroachment on land vested in the Corporation)",
  "HMCA_408A", ["SCN_408A", "EVICTION_DEMOLITION_ORDER_408A", "STOP_WORK_262", "SEALING_263A"], 7, 7, "CRITICAL", "NO", GOVT_EVIDENCE, 500, None,
  notes="Competent authority is the Joint Commissioner (s.2(4A)). Notice may be served by post, in person or by affixation / beat of drum (s.408A(1)). Cost of demolition recoverable as arrears of land revenue."),
v("GL-02", GL, "Encroachment / unauthorised construction on State Government land or other public premises",
  "राज्य सरकार की भूमि / अन्य सार्वजनिक परिसर पर अतिक्रमण / अनधिकृत निर्माण",
  """Construction on land belonging to the State Government or a Government department/board/corporation (e.g., HSVP, GMDA, PWD, Irrigation, Forest, Panchayat land not vested in MCG). MCG records the violation, issues stop-work / demolition proceedings for the building under the HMC Act and refers eviction to the Collector under the Public Premises Act.""",
  [{"statute": HPPA, "section": "3"}, {"statute": HPPA, "section": "4"}, {"statute": HPPA, "section": "5"}, {"statute": HPPA, "section": "7(2)-(3)"}, {"statute": HMCA, "section": "254(2)(e)"}, {"statute": HMCA, "section": "250"}, {"statute": HMCA, "section": "261(1)"}, {"statute": HMCA, "section": "262(1)"}],
  "Section 3 of the Haryana Public Premises and Land (Eviction and Rent Recovery) Act, 1972 read with sections 250 and 254(2)(e) of the Haryana Municipal Corporation Act, 1994",
  "HPPA_4_5", ["SCN_261", "STOP_WORK_262", "DEMOLITION_ORDER_261", "SEALING_263A", "REFERRAL_TO_COLLECTOR_HPPA"], 10, 15, "CRITICAL", "NO", GOVT_EVIDENCE + ["Letter / e-mail to the land-owning department and the Collector (DC) office"], 5000, 500,
  notes="Eviction under HPPA is by the Collector (DC/SDM). The system generates the referral letter and tracks the DC-office reference; the building itself is proceeded against under s.261 (no sanction possible on Government land, s.254(2)(e))."),
v("GL-03", ST, "Structure / fixture erected on public street, footpath or road land",
  "सार्वजनिक सड़क, फुटपाथ या रोड-लैंड पर संरचना / फिक्सचर का निर्माण",
  """Walls, fences, rails, posts, steps, ramps, booths, kiosks, sheds or any permanent or temporary structure or fixture erected on any street or footpath, or over a drain, channel or well in a street, forming an obstruction or encroachment.""",
  [{"statute": HMCA, "section": "238(1)"}, {"statute": HMCA, "section": "235(1)"}, {"statute": HMCA, "section": "235(2)"}, {"statute": HMCA, "section": "240"}, {"statute": HMCA, "section": "216"}],
  "Sections 235 and 238(1) of the Haryana Municipal Corporation Act, 1994",
  "HMCA_235_238", ["REMOVAL_NOTICE_235", "SUMMARY_REMOVAL_240", "SCN_261", "DEMOLITION_ORDER_261"], 3, 3, "HIGH", "NO", COMMON_EVIDENCE + ["Measurement of the encroached width of the street/footpath", "Road/street name and right-of-way width"], 1000, 100),
v("GL-04", ST, "Construction within the regular line of a street / building line",
  "सड़क की नियमित रेखा / भवन रेखा के भीतर निर्माण",
  """Any portion of a building erected, re-erected or added within the regular line of a public street or the building line fixed by the Corporation, or in contravention of a sanctioned scheme/plan.""",
  [{"statute": HMCA, "section": "224"}, {"statute": HMCA, "section": "258(2)"}, {"statute": HMCA, "section": "252(1)(e)"}, {"statute": HMCA, "section": "261(1)"}],
  "Sections 224/225 and 258(2) of the Haryana Municipal Corporation Act, 1994",
  "HMCA_261", ["SCN_261", "STOP_WORK_262", "DEMOLITION_ORDER_261"], 7, 15, "HIGH", "NO", COMMON_EVIDENCE + ["Regular line of street / building line from the sanctioned layout", "Measured distance of the structure from the road centre line"], 1000, None),
v("GL-05", ST, "Projection over street without permission (balcony, canopy, sunshade, ramp, steps)",
  "बिना अनुमति सड़क पर प्रक्षेपण (बालकनी, कैनोपी, छज्जा, रैम्प, सीढ़ियाँ)",
  """Balconies, canopies, chajjas, awnings, signboards, ramps, steps or other things projecting over or on to a street beyond the plot boundary without written permission of the Commissioner, or beyond the permitted extent.""",
  [{"statute": HMCA, "section": "235(1)"}, {"statute": HMCA, "section": "236"}, {"statute": HMCA, "section": "235(2)"}, {"statute": HBC, "section": "7.12"}],
  "Sections 235 and 236 of the Haryana Municipal Corporation Act, 1994 read with Code 7.12 of the Haryana Building Code, 2017",
  "HMCA_235_238", ["REMOVAL_NOTICE_235", "SUMMARY_REMOVAL_240", "SCN_261"], 7, 7, "MEDIUM", "CONDITIONAL", COMMON_EVIDENCE + ["Measured projection beyond plot line (metres)"], 500, 50),
v("GL-06", GL, "Construction on or over a municipal drain, nallah, water body, pond or johad",
  "नगरपालिका नाले, नाली, जलाशय, तालाब या जोहड़ पर / के ऊपर निर्माण",
  """Structures raised on, over or into a municipal drain, storm-water nallah, natural water course, pond/johad or its embankment so as to interfere with its working, inspection or cleansing, or encroach upon land vested in the Corporation.""",
  [{"statute": HMCA, "section": "235(1)"}, {"statute": HMCA, "section": "238(1)"}, {"statute": HMCA, "section": "408"}, {"statute": HMCA, "section": "408A(1)"}, {"statute": HMCA, "section": "261(1)"}],
  "Sections 235(1)(b), 238(1) and 408/408A of the Haryana Municipal Corporation Act, 1994",
  "HMCA_408A", ["SCN_408A", "EVICTION_DEMOLITION_ORDER_408A", "STOP_WORK_262", "DEMOLITION_ORDER_261"], 7, 7, "CRITICAL", "NO", GOVT_EVIDENCE + ["Drain/nallah name and the GIS drainage layer screenshot"], 1000, 100,
  notes="Water bodies: also check Haryana Pond and Waste Water Management Authority Act, 2018 and NGT directions; refer to the Executive Engineer (Drainage)."),
v("GL-07", GL, "Construction on land reserved for public purpose in a sanctioned scheme / layout (park, green belt, community site, road)",
  "स्वीकृत योजना / लेआउट में सार्वजनिक प्रयोजन हेतु आरक्षित भूमि (पार्क, ग्रीन बेल्ट, सामुदायिक स्थल, सड़क) पर निर्माण",
  """Buildings on sites earmarked in the sanctioned layout / development plan / building scheme for parks, open spaces, roads, community facilities or other public purposes.""",
  [{"statute": HMCA, "section": "254(2)(g)"}, {"statute": HMCA, "section": "258(2)"}, {"statute": HMCA, "section": "267"}, {"statute": HMCA, "section": "261(1)"}, {"statute": PSRCA, "section": "7"}, {"statute": PSRCA, "section": "12(1)"}],
  "Sections 254(2)(g), 258(2) and 267 of the Haryana Municipal Corporation Act, 1994 (and section 7 of the Punjab Scheduled Roads and Controlled Areas Restriction of Unregulated Development Act, 1963 where the site is in a controlled area)",
  "HMCA_261", ["SCN_261", "STOP_WORK_262", "SEALING_263A", "DEMOLITION_ORDER_261", "REFERRAL_TO_DTCP"], 7, 15, "CRITICAL", "NO", GOVT_EVIDENCE + ["Extract of sanctioned layout / zoning plan showing reservation"], 1000, None),
v("GL-08", ST, "Deposit of building material / malba on street or public land without permission",
  "बिना अनुमति सड़क या सार्वजनिक भूमि पर निर्माण सामग्री / मलबा जमा करना",
  """Building material, debris (malba), sand, bricks, scaffolding or enclosures placed on a street or public place without written permission of the Commissioner.""",
  [{"statute": HMCA, "section": "243(1)"}, {"statute": HMCA, "section": "243(3)"}, {"statute": HMCA, "section": "238(2)"}, {"statute": HMCA, "section": "244"}],
  "Sections 238(2) and 243(1) of the Haryana Municipal Corporation Act, 1994 (also Construction & Demolition Waste Management Rules, 2016)",
  "HMCA_235_238", ["REMOVAL_NOTICE_235", "SUMMARY_REMOVAL_240"], 1, 1, "LOW", "YES", COMMON_EVIDENCE, 500, 50,
  notes="Summary removal without notice permitted (s.243(3)); link the C&D waste challan module for the malba lifting charge."),

# --- B. Unauthorised construction on private land (no sanction) --------------
v("PL-01", PL, "Erection of building without sanction of building plan",
  "भवन योजना की स्वीकृति के बिना भवन का निर्माण",
  """New construction commenced, in progress or completed on a private plot without the previous sanction of the Commissioner (no BR-I application / no sanctioned plan / no self-certification intimation).""",
  [{"statute": HMCA, "section": "250"}, {"statute": HMCA, "section": "251"}, {"statute": HMCA, "section": "261(1)"}, {"statute": HMCA, "section": "262(1)"}, {"statute": HMCA, "section": "263A(1)"}, {"statute": HBC, "section": "2.1(1)"}, {"statute": HBC, "section": "2.2(4)"}],
  "Section 250 read with section 251 of the Haryana Municipal Corporation Act, 1994 and Code 2.1 of the Haryana Building Code, 2017",
  "HMCA_261", ["SCN_261", "STOP_WORK_262", "SEALING_263A", "DEMOLITION_ORDER_261"], 7, 15, "CRITICAL", "CONDITIONAL", DEV_EVIDENCE, 5000, 500,
  notes="Regularisation possible only if the construction is otherwise in conformity with the Code and a plan is sanctioned with composition charges; ground-coverage violations are non-compoundable (HBC 6.3)."),
v("PL-02", PL, "Addition / alteration / structural repair without sanction",
  "स्वीकृति के बिना जोड़ / परिवर्तन / संरचनात्मक मरम्मत",
  """Additional floor, room, extension, removal or re-erection of external/partition/load-bearing walls, sub-division of rooms, closing of external openings, relocation of principal staircase or other works listed in section 252 executed without sanction.""",
  [{"statute": HMCA, "section": "252"}, {"statute": HMCA, "section": "250"}, {"statute": HMCA, "section": "261(1)"}, {"statute": HMCA, "section": "263"}, {"statute": HBC, "section": "4.6"}],
  "Sections 250 and 252 of the Haryana Municipal Corporation Act, 1994 and Code 4.6 of the Haryana Building Code, 2017",
  "HMCA_261", ["SCN_261", "STOP_WORK_262", "ALTERATION_NOTICE_263", "DEMOLITION_ORDER_261"], 7, 15, "HIGH", "CONDITIONAL", DEV_EVIDENCE, 500, 50),
v("PL-03", PL, "Construction continued after expiry / lapse of sanction validity",
  "स्वीकृति की वैधता समाप्त होने के बाद निर्माण जारी रखना",
  """Work continued beyond the completion period specified in the sanction or after the sanction lapsed without re-validation / fresh sanction.""",
  [{"statute": HMCA, "section": "259"}, {"statute": HMCA, "section": "255(3)"}, {"statute": HBC, "section": "4.3-4.4"}, {"statute": HMCA, "section": "261(1)"}],
  "Section 259 read with section 255(3) of the Haryana Municipal Corporation Act, 1994 and Codes 4.3-4.4 of the Haryana Building Code, 2017",
  "HMCA_261", ["SCN_261", "STOP_WORK_262", "DEMOLITION_ORDER_261"], 7, 15, "MEDIUM", "YES", DEV_EVIDENCE + ["Sanction letter showing validity / completion period"], 2000, 200),
v("PL-04", PL, "Sanction obtained by misrepresentation or fraudulent documents",
  "गलत बयानी या कूटरचित दस्तावेज़ों से प्राप्त स्वीकृति",
  """Sanction/self-certification found to be based on material misrepresentation, forged ownership papers or false certificates; on cancellation the construction is deemed to be without sanction.""",
  [{"statute": HMCA, "section": "256"}, {"statute": HBC, "section": "4.7"}, {"statute": HMCA, "section": "261(1)"}],
  "Section 256 of the Haryana Municipal Corporation Act, 1994 and Code 4.7 of the Haryana Building Code, 2017",
  "HMCA_261", ["SCN_256_CANCELLATION", "SCN_261", "STOP_WORK_262", "SEALING_263A", "DEMOLITION_ORDER_261"], 7, 15, "CRITICAL", "NO", DEV_EVIDENCE + ["Copy of the impugned document and the verification report (revenue / registrar)"], 5000, 500,
  notes="Also refer the Architect to the Council of Architecture (HBC 2.2(3)) and consider a police complaint for forgery (BNS 2023 ss.336-340)."),
v("PL-05", PROC, "Commencement of work without notice of commencement / DPC certificate",
  "प्रारंभ की सूचना / डी.पी.सी. प्रमाण-पत्र के बिना कार्य प्रारंभ",
  """Construction started without giving the notice of the proposed date of commencement (and DPC-level certificate) required after sanction.""",
  [{"statute": HMCA, "section": "255(4)"}, {"statute": HBC, "section": "4.9"}],
  "Section 255(4) of the Haryana Municipal Corporation Act, 1994 and Code 4.9 of the Haryana Building Code, 2017",
  "HMCA_263", ["ALTERATION_NOTICE_263", "STOP_WORK_262"], 7, 7, "LOW", "YES", DEV_EVIDENCE, 2000, 200),
v("PL-06", PL, "Illegal colony / unauthorised plotting or layout / roads laid without sanction",
  "अवैध कॉलोनी / अनधिकृत प्लॉटिंग या लेआउट / बिना स्वीकृति सड़कें बनाना",
  """Land divided into plots, streets laid out, boundary walls/plinths raised or plots sold on the ground without a sanctioned layout plan / licence.""",
  [{"statute": HMCA, "section": "230"}, {"statute": HMCA, "section": "231"}, {"statute": HMCA, "section": "232"}, {"statute": HMCA, "section": "254(2)(d)"}, {"statute": HMCA, "section": "261(1)"}, {"statute": PSRCA, "section": "7"}, {"statute": PSRCA, "section": "12(1)"}],
  "Sections 230-232 and 254(2)(d) of the Haryana Municipal Corporation Act, 1994 (and section 7 of the 1963 Act / section 3 of the Haryana Development and Regulation of Urban Areas Act, 1975 where applicable)",
  "HMCA_261", ["SCN_261", "STOP_WORK_262", "DEMOLITION_ORDER_261", "REFERRAL_TO_DTCP"], 7, 15, "CRITICAL", "NO", COMMON_EVIDENCE + ["Drone / satellite imagery of the layout", "Khasra numbers and area under plotting", "Details of the coloniser / developer and any sale deeds"], 1000, None,
  notes="Co-ordinate with DTP (Enforcement) where the land is in a controlled area outside the sanctioned layout; the app generates the referral."),

# --- C. Deviation from sanctioned plan --------------------------------------
v("DV-01", DEV, "Construction contrary to sanctioned plan / in contravention of conditions of sanction",
  "स्वीकृत नक्शे के विपरीत / स्वीकृति की शर्तों का उल्लंघन करते हुए निर्माण",
  """Any deviation from the sanctioned drawings or the conditions of sanction not covered by a revised sanction (general head; use the specific codes below where the deviation is identifiable).""",
  [{"statute": HMCA, "section": "255(2)"}, {"statute": HMCA, "section": "261(1)"}, {"statute": HMCA, "section": "262(1)"}, {"statute": HMCA, "section": "263"}, {"statute": HBC, "section": "4.6"}, {"statute": HBC, "section": "2.2(4)"}],
  "Section 255(2) of the Haryana Municipal Corporation Act, 1994 and Code 4.6 of the Haryana Building Code, 2017",
  "HMCA_263", ["ALTERATION_NOTICE_263", "SCN_261", "STOP_WORK_262", "SEALING_263A", "DEMOLITION_ORDER_261"], 7, 15, "HIGH", "CONDITIONAL", DEV_EVIDENCE, 2000, 200),
v("DV-02", DEV, "Ground coverage in excess of permissible limit",
  "अनुमेय सीमा से अधिक ग्राउंड कवरेज",
  """Covered area at ground/any floor exceeding the permissible ground coverage for the plot category; non-compoundable under the Code.""",
  [{"statute": HBC, "section": "6.3"}, {"statute": HMCA, "section": "255(2)"}, {"statute": HMCA, "section": "261(1)"}],
  "Code 6.3 of the Haryana Building Code, 2017 read with section 255(2) of the Haryana Municipal Corporation Act, 1994",
  "HMCA_261", ["SCN_261", "STOP_WORK_262", "SEALING_263A", "DEMOLITION_ORDER_261"], 7, 15, "HIGH", "NO", DEV_EVIDENCE + ["Measured coverage (sq m) vs permitted (sq m and %)"], 2000, 200),
v("DV-03", DEV, "Floor Area Ratio (FAR) / additional floor beyond permissible",
  "अनुमेय से अधिक एफ.ए.आर. / अतिरिक्त मंज़िल",
  """Total covered area exceeding the permissible FAR, or floors constructed beyond the number sanctioned/permissible for the plot (e.g., 5th floor on a plot permitted S+4).""",
  [{"statute": HBC, "section": "6.3"}, {"statute": HMCA, "section": "255(2)"}, {"statute": HMCA, "section": "261(1)"}, {"statute": HMCA, "section": "263A(1)"}],
  "Code 6.3 (FAR) of the Haryana Building Code, 2017 read with section 255(2) of the Haryana Municipal Corporation Act, 1994",
  "HMCA_261", ["SCN_261", "STOP_WORK_262", "SEALING_263A", "DEMOLITION_ORDER_261"], 7, 15, "HIGH", "CONDITIONAL", DEV_EVIDENCE + ["Measured FAR vs permitted FAR", "Number of floors sanctioned vs constructed"], 2000, 200,
  notes="Purchasable FAR / composition may regularise excess FAR only within the limits and on the charges notified by the Government."),
v("DV-04", DEV, "Violation of front / side / rear setbacks",
  "आगे / बगल / पीछे के सेटबैक का उल्लंघन",
  """Construction within the mandatory open spaces (setbacks) around the building, including covering of setbacks with rooms, porticos beyond limits or sheds.""",
  [{"statute": HBC, "section": "6.3"}, {"statute": HMCA, "section": "263"}, {"statute": HMCA, "section": "261(1)"}],
  "Code 6.3 (setbacks) of the Haryana Building Code, 2017 read with sections 255(2) and 263 of the Haryana Municipal Corporation Act, 1994",
  "HMCA_263", ["ALTERATION_NOTICE_263", "SCN_261", "DEMOLITION_ORDER_261"], 7, 15, "HIGH", "CONDITIONAL", DEV_EVIDENCE + ["Measured setbacks (m) on each side vs required"], 2000, 200),
v("DV-05", DEV, "Building height beyond permissible",
  "अनुमेय से अधिक भवन की ऊँचाई",
  """Height of building (including mumty/parapet where counted) exceeding the permissible height for the plot / zone (e.g., 15 m for residential plotted with stilt).""",
  [{"statute": HBC, "section": "6.3"}, {"statute": HMCA, "section": "261(1)"}],
  "Code 6.3 (height) of the Haryana Building Code, 2017 read with section 255(2) of the Haryana Municipal Corporation Act, 1994",
  "HMCA_261", ["SCN_261", "STOP_WORK_262", "DEMOLITION_ORDER_261"], 7, 15, "HIGH", "NO", DEV_EVIDENCE + ["Measured height (m) vs permitted"], 2000, 200),
v("DV-06", DEV, "Basement constructed without sanction / beyond permitted extent or misused",
  "स्वीकृति के बिना / अनुमत सीमा से अधिक बेसमेंट या उसका दुरुपयोग",
  """Basement dug or built without sanction, extending beyond the permitted footprint/setbacks, or used for habitation/commerce against the Code.""",
  [{"statute": HBC, "section": "7.16"}, {"statute": HMCA, "section": "250"}, {"statute": HMCA, "section": "261(1)"}, {"statute": HMCA, "section": "265(1)"}],
  "Code 7.16 of the Haryana Building Code, 2017 read with sections 250 and 265(1) of the Haryana Municipal Corporation Act, 1994",
  "HMCA_261", ["SCN_261", "STOP_WORK_262", "SEALING_263A", "DEMOLITION_ORDER_261"], 7, 15, "HIGH", "NO", DEV_EVIDENCE + ["Structural safety concern noted (adjoining buildings)"], 2000, 200),
v("DV-07", DEV, "Stilt parking covered / converted or parking not provided as sanctioned",
  "स्टिल्ट पार्किंग को ढकना / बदलना या स्वीकृत पार्किंग उपलब्ध न कराना",
  """Stilt floor sanctioned for parking enclosed into rooms/shops, or mandatory parking spaces used for other purposes.""",
  [{"statute": HBC, "section": "6.3"}, {"statute": HBC, "section": "7.1"}, {"statute": HMCA, "section": "263"}, {"statute": HMCA, "section": "265(1)"}],
  "Codes 6.3 and 7.1 of the Haryana Building Code, 2017 read with sections 263 and 265(1) of the Haryana Municipal Corporation Act, 1994",
  "HMCA_263", ["ALTERATION_NOTICE_263", "SCN_261", "SEALING_263A", "DEMOLITION_ORDER_261"], 7, 15, "MEDIUM", "NO", DEV_EVIDENCE, 1000, 100),
v("DV-08", DEV, "Unauthorised sub-division of plot / more than one building unit on a plot",
  "प्लॉट का अनधिकृत उप-विभाजन / एक प्लॉट पर एक से अधिक भवन इकाई",
  """Plot split into independent units with separate access/staircases, or more dwelling units than permitted, without approval.""",
  [{"statute": HBC, "section": "6.2(1)-(2)"}, {"statute": HMCA, "section": "254(2)(d)"}, {"statute": HMCA, "section": "261(1)"}],
  "Code 6.2 of the Haryana Building Code, 2017 read with section 254(2)(d) of the Haryana Municipal Corporation Act, 1994",
  "HMCA_261", ["SCN_261", "STOP_WORK_262", "SEALING_263A", "DEMOLITION_ORDER_261"], 7, 15, "HIGH", "NO", DEV_EVIDENCE + ["Number of independent units / kitchens / meters"], 2000, 200),
v("DV-09", DEV, "Unauthorised amalgamation of plots",
  "प्लॉटों का अनधिकृत समामेलन",
  """Two or more plots built upon as one unit without approval of amalgamation or in violation of the zoning for the amalgamated plot.""",
  [{"statute": HBC, "section": "6.2(1)-(2)"}, {"statute": HMCA, "section": "261(1)"}],
  "Code 6.2 of the Haryana Building Code, 2017",
  "HMCA_263", ["ALTERATION_NOTICE_263", "SCN_261", "DEMOLITION_ORDER_261"], 7, 15, "MEDIUM", "CONDITIONAL", DEV_EVIDENCE, 2000, 200),
v("DV-10", DEV, "Violation of zoning plan / architectural control sheet",
  "ज़ोनिंग प्लान / आर्किटेक्चरल कंट्रोल शीट का उल्लंघन",
  """Building not conforming to the zoning plan or architectural control sheet applicable to the plot (e.g., shop-cum-flat sites, booths, sector commercial).""",
  [{"statute": HBC, "section": "3.5"}, {"statute": HBC, "section": "6.4"}, {"statute": HMCA, "section": "261(1)"}],
  "Codes 3.5 and 6.4 of the Haryana Building Code, 2017 read with section 255(2) of the Haryana Municipal Corporation Act, 1994",
  "HMCA_263", ["ALTERATION_NOTICE_263", "SCN_261", "DEMOLITION_ORDER_261"], 7, 15, "MEDIUM", "CONDITIONAL", DEV_EVIDENCE + ["Copy of the zoning plan / control sheet"], 2000, 200),
v("DV-11", DEV, "Mezzanine, mumty, pergola, chajja or projection beyond permitted limits",
  "अनुमत सीमा से अधिक मेज़ेनाइन, मुमटी, पेर्गोला, छज्जा या प्रक्षेपण",
  """Mezzanine floors, mumty, pergolas, chajjas or cantilevered projections exceeding the dimensions permitted by the Code.""",
  [{"statute": HBC, "section": "7.12"}, {"statute": HBC, "section": "7.13"}, {"statute": HMCA, "section": "263"}],
  "Codes 7.12 and 7.13 of the Haryana Building Code, 2017 read with section 263 of the Haryana Municipal Corporation Act, 1994",
  "HMCA_263", ["ALTERATION_NOTICE_263", "SCN_261"], 7, 15, "LOW", "YES", DEV_EVIDENCE, 2000, None),

# --- D. Misuse / change of use / occupation ---------------------------------
v("MU-01", MIS, "Change of use of land or building without permission (e.g., residential to commercial, PG, guest house, godown)",
  "बिना अनुमति भूमि या भवन के उपयोग में परिवर्तन (जैसे आवासीय से व्यावसायिक, पी.जी., गेस्ट हाउस, गोदाम)",
  """Use of premises for a purpose other than the sanctioned/permitted use without written permission of the Commissioner or Change of Land Use.""",
  [{"statute": HMCA, "section": "265(1)"}, {"statute": HBC, "section": "4.12"}, {"statute": HBC, "section": "6.1"}, {"statute": HMCA, "section": "263A(1)"}],
  "Section 265(1)(b) of the Haryana Municipal Corporation Act, 1994 and Codes 4.12 and 6.1 of the Haryana Building Code, 2017",
  "HMCA_265_1", ["MISUSE_NOTICE_265", "SEALING_263A", "OC_REVOCATION_HBC_4_12"], 7, 15, "HIGH", "CONDITIONAL", COMMON_EVIDENCE + ["Photographs of signage / commercial activity", "Trade licence / GST / electricity connection category if available"], 1000, 100,
  notes="Sealing under s.263A is available where the misuse is coupled with unauthorised construction; otherwise proceed under s.265(1), OC revocation and prosecution u/s 380."),
v("MU-02", MIS, "Occupation / use of building without completion / occupation certificate",
  "पूर्णता / अधिभोग प्रमाण-पत्र के बिना भवन का अधिभोग / उपयोग",
  """Building or part occupied or used before the completion notice was given and occupation permission (OC) granted / deemed.""",
  [{"statute": HMCA, "section": "264"}, {"statute": HBC, "section": "4.10(2)"}, {"statute": HMCA, "section": "266"}],
  "Section 264(2) of the Haryana Municipal Corporation Act, 1994 and Code 4.10(2) of the Haryana Building Code, 2017",
  "HMCA_266", ["OC_NOTICE_264", "VACATE_ORDER_266", "SEALING_263A"], 7, 15, "MEDIUM", "YES", COMMON_EVIDENCE + ["Evidence of occupation (residents, electricity/water connection)"], 500, 50),
v("MU-03", MIS, "Use of inflammable materials for roof / shed / pandal without permission",
  "बिना अनुमति छत / शेड / पंडाल में ज्वलनशील सामग्री का उपयोग",
  """Roof, verandah, pandal, wall, shed or fence constructed of cloth, grass, leaves, mats or other inflammable material in an area specified by bye-laws without written permission.""",
  [{"statute": HMCA, "section": "260"}],
  "Section 260 of the Haryana Municipal Corporation Act, 1994",
  "HMCA_235_238", ["REMOVAL_NOTICE_235", "SUMMARY_REMOVAL_240"], 3, 3, "LOW", "YES", COMMON_EVIDENCE, 1000, None),

# --- E. Dangerous / unfit buildings ------------------------------------------
v("DB-01", DAN, "Dangerous / ruinous structure likely to fall",
  "खतरनाक / जर्जर संरचना जिसके गिरने की संभावना है",
  """Building or wall in a ruinous condition, likely to fall or otherwise dangerous to occupants, neighbours or passers-by.""",
  [{"statute": HMCA, "section": "265(2)-(6)"}, {"statute": HMCA, "section": "315"}, {"statute": HMCA, "section": "266"}],
  "Sections 265(2) and 315 of the Haryana Municipal Corporation Act, 1994",
  "HMCA_265_2", ["DANGEROUS_BUILDING_ORDER_265", "VACATE_ORDER_266", "IMMEDIATE_ACTION_265_4"], 3, 7, "CRITICAL", "NO", COMMON_EVIDENCE + ["Structural condition photographs (cracks, tilt)", "Engineer's preliminary assessment"], 2000, 200),
v("DB-02", DAN, "Building unfit for human habitation",
  "मानव निवास के लिए अनुपयुक्त भवन",
  """Building unfit for human habitation and not capable of being rendered fit at reasonable expense (repair, stability, damp, light/air, water, drainage, sanitation).""",
  [{"statute": HMCA, "section": "284"}, {"statute": HMCA, "section": "282"}],
  "Sections 282 to 284 of the Haryana Municipal Corporation Act, 1994",
  "HMCA_284", ["SCN_284", "DEMOLITION_ORDER_284", "VACATE_ORDER_266"], 30, 42, "HIGH", "NO", COMMON_EVIDENCE + ["Health Officer / Engineer inspection report"], 2000, 200,
  notes="Statutory sequence: SCN -> undertaking (284(2)) -> demolition order with >=30 days to vacate and demolition within 6 weeks thereafter (284(3))."),

# --- F. Procedural / post-order non-compliance ------------------------------
v("PN-01", PROC, "Continuing construction after stop-work order",
  "कार्य-रोक आदेश के बाद निर्माण जारी रखना",
  """Erection or work continued after service of a stop-work order under s.262(1) / s.261 second proviso.""",
  [{"statute": HMCA, "section": "262(2)"}, {"statute": HMCA, "section": "262(3)"}, {"statute": HMCA, "section": "262(4)"}, {"statute": HMCA, "section": "380"}, {"statute": BNS, "section": "223"}],
  "Section 262(2) of the Haryana Municipal Corporation Act, 1994 (disobedience of stop-work order) read with section 223 of the Bharatiya Nyaya Sanhita, 2023",
  "HMCA_261", ["POLICE_REQUISITION_262_2", "WATCH_DEPUTATION_262_3", "SEALING_263A", "DEMOLITION_ORDER_261", "PROSECUTION_380"], 0, 3, "CRITICAL", "NO", COMMON_EVIDENCE + ["Copy of the stop-work order and proof of service", "Dated photographs showing progress after service"], 2000, 200),
v("PN-02", PROC, "Failure to comply with demolition order / alteration notice",
  "ध्वस्तीकरण आदेश / परिवर्तन नोटिस का पालन न करना",
  """Person on whom a demolition order (s.261/408A) or alteration notice (s.263) was served has not complied within the period specified.""",
  [{"statute": HMCA, "section": "261(6)"}, {"statute": HMCA, "section": "263"}, {"statute": HMCA, "section": "408A(3)"}, {"statute": HMCA, "section": "380"}],
  "Sections 261(6), 263(2) and 408A(3) of the Haryana Municipal Corporation Act, 1994",
  "HMCA_261", ["EXECUTION_BY_CORPORATION", "COST_RECOVERY", "PROSECUTION_380"], 0, 0, "CRITICAL", "NO", COMMON_EVIDENCE + ["Copy of order and proof of service", "Photographs on the day after expiry"], 2000, 200),
v("PN-03", PROC, "Breaking / removal of seal",
  "सील तोड़ना / हटाना",
  """Seal affixed under s.263A removed or broken without an order of the Commissioner or the appellate authority.""",
  [{"statute": HMCA, "section": "263A(3)"}, {"statute": HMCA, "section": "380"}, {"statute": BNS, "section": "223"}],
  "Section 263A(3) of the Haryana Municipal Corporation Act, 1994 read with section 223 of the Bharatiya Nyaya Sanhita, 2023",
  "HMCA_261", ["RESEALING_263A", "POLICE_COMPLAINT", "DEMOLITION_ORDER_261", "PROSECUTION_380"], 0, 3, "CRITICAL", "NO", COMMON_EVIDENCE + ["Photograph of the broken seal with the sealing memo number", "Police DDR / FIR number"], 2000, 200),
v("PN-04", PROC, "Removal / defacing of notice affixed on premises",
  "परिसर पर चस्पा नोटिस को हटाना / विरूपित करना",
  """Notice/order affixed on the premises removed, destroyed or defaced without authority.""",
  [{"statute": HMCA, "section": "407"}, {"statute": HMCA, "section": "380"}],
  "Section 407 of the Haryana Municipal Corporation Act, 1994",
  "HMCA_261", ["RE_AFFIXATION", "PROSECUTION_380"], 0, 0, "LOW", "YES", ["Geotagged photo of the affixed notice (from delivery proof)", "Geotagged photo showing removal / defacement"], 500, None),
v("PN-05", PROC, "Obstruction of Corporation officials during inspection / enforcement",
  "निरीक्षण / प्रवर्तन के दौरान निगम अधिकारियों को बाधा पहुँचाना",
  """Officials obstructed, threatened or prevented from inspecting the premises or executing an order.""",
  [{"statute": HMCA, "section": "405"}, {"statute": HMCA, "section": "380"}, {"statute": BNS, "section": "221"}],
  "Section 405 of the Haryana Municipal Corporation Act, 1994 read with section 221 of the Bharatiya Nyaya Sanhita, 2023",
  "HMCA_261", ["POLICE_REQUISITION_262_2", "POLICE_COMPLAINT", "PROSECUTION_380"], 0, 0, "HIGH", "NO", ["Video of the incident", "Names / description of persons obstructing", "Police DDR number"], 500, None),
v("PL-07", PL, "Construction in controlled area / scheduled-road restricted belt without CLU / permission",
  "नियंत्रित क्षेत्र / अनुसूचित सड़क प्रतिबंधित पट्टी में सी.एल.यू. / अनुमति के बिना निर्माण",
  """Building within a controlled area or the restricted belt along a scheduled road, without Change of Land Use / permission of the Director, Town & Country Planning, where the area lies within municipal limits.""",
  [{"statute": PSRCA, "section": "3"}, {"statute": PSRCA, "section": "7"}, {"statute": PSRCA, "section": "12(1)"}, {"statute": PSRCA, "section": "12(2)-(3)"}, {"statute": HMCA, "section": "346(1)"}, {"statute": HMCA, "section": "250"}],
  "Sections 3 and 7 of the Punjab Scheduled Roads and Controlled Areas Restriction of Unregulated Development Act, 1963 read with section 250 of the Haryana Municipal Corporation Act, 1994",
  "HMCA_261", ["SCN_261", "STOP_WORK_262", "DEMOLITION_ORDER_261", "REFERRAL_TO_DTCP"], 7, 15, "HIGH", "NO", DEV_EVIDENCE + ["Controlled-area / scheduled-road layer screenshot"], 5000, 500,
  notes="Where DTCP is the enforcing authority, MCG issues the referral and continues proceedings for the building under the HMC Act."),
]

# Order types (used by the JC decision screen and the PDF generator)
order_types = {
    "SCN_261": {"title_en": "Show Cause Notice under section 261(1) proviso (why the unauthorised erection/work should not be demolished)", "title_hi": "धारा 261(1) के परंतुक के अंतर्गत कारण बताओ नोटिस", "statute": HMCA, "section": "261(1)", "kind": "NOTICE", "min_days": 0, "default_days": 7, "template": "scn_261.html"},
    "SCN_408A": {"title_en": "Show Cause Notice under section 408A(1) (unauthorised occupation of Corporation land)", "title_hi": "धारा 408A(1) के अंतर्गत कारण बताओ नोटिस", "statute": HMCA, "section": "408A(1)", "kind": "NOTICE", "min_days": 7, "default_days": 7, "template": "scn_408a.html"},
    "SCN_284": {"title_en": "Show Cause Notice under section 284(1) (building unfit for human habitation)", "title_hi": "धारा 284(1) के अंतर्गत कारण बताओ नोटिस", "statute": HMCA, "section": "284", "kind": "NOTICE", "min_days": 0, "default_days": 30, "template": "scn_284.html"},
    "SCN_256_CANCELLATION": {"title_en": "Show Cause Notice under section 256 (cancellation of sanction obtained by misrepresentation)", "title_hi": "धारा 256 के अंतर्गत कारण बताओ नोटिस (स्वीकृति निरस्तीकरण)", "statute": HMCA, "section": "256", "kind": "NOTICE", "min_days": 0, "default_days": 7, "template": "scn_256.html"},
    "ALTERATION_NOTICE_263": {"title_en": "Notice under section 263(1) requiring alteration of work / show cause", "title_hi": "धारा 263(1) के अंतर्गत कार्य में परिवर्तन हेतु नोटिस", "statute": HMCA, "section": "263", "kind": "NOTICE", "min_days": 0, "default_days": 7, "template": "notice_263.html"},
    "REMOVAL_NOTICE_235": {"title_en": "Notice under section 235(2) to remove projection / structure from street", "title_hi": "धारा 235(2) के अंतर्गत सड़क से प्रक्षेपण / संरचना हटाने का नोटिस", "statute": HMCA, "section": "235(2)", "kind": "NOTICE", "min_days": 0, "default_days": 3, "template": "notice_235.html"},
    "MISUSE_NOTICE_265": {"title_en": "Notice under section 265(1) to discontinue unauthorised use / change of use", "title_hi": "धारा 265(1) के अंतर्गत अनधिकृत उपयोग बंद करने का नोटिस", "statute": HMCA, "section": "265(1)", "kind": "NOTICE", "min_days": 0, "default_days": 7, "template": "notice_265_1.html"},
    "OC_NOTICE_264": {"title_en": "Notice under section 264(2) - occupation without completion / occupation certificate", "title_hi": "धारा 264(2) के अंतर्गत नोटिस - अधिभोग प्रमाण-पत्र के बिना अधिभोग", "statute": HMCA, "section": "264", "kind": "NOTICE", "min_days": 0, "default_days": 7, "template": "notice_264.html"},
    "STOP_WORK_262": {"title_en": "Stop-Work Order under section 262(1)", "title_hi": "धारा 262(1) के अंतर्गत कार्य-रोक आदेश", "statute": HMCA, "section": "262(1)", "kind": "ORDER", "min_days": 0, "default_days": 0, "template": "order_stop_work_262.html"},
    "SEALING_263A": {"title_en": "Sealing Order under section 263A(1)", "title_hi": "धारा 263A(1) के अंतर्गत सीलिंग आदेश", "statute": HMCA, "section": "263A(1)", "kind": "ORDER", "min_days": 0, "default_days": 0, "template": "order_sealing_263a.html", "appeal_days": 7, "appeal_to": "Divisional Commissioner, Gurugram"},
    "RESEALING_263A": {"title_en": "Re-sealing memo under section 263A", "title_hi": "धारा 263A के अंतर्गत पुनः सीलिंग ज्ञापन", "statute": HMCA, "section": "263A(3)", "kind": "ORDER", "min_days": 0, "default_days": 0, "template": "order_sealing_263a.html"},
    "DEMOLITION_ORDER_261": {"title_en": "Demolition Order under section 261(1)", "title_hi": "धारा 261(1) के अंतर्गत ध्वस्तीकरण आदेश", "statute": HMCA, "section": "261(1)", "kind": "ORDER", "min_days": 3, "default_days": 15, "template": "order_demolition_261.html", "appeal_days": None, "appeal_to": "Divisional Commissioner, Gurugram (within the period specified in this order)"},
    "EVICTION_DEMOLITION_ORDER_408A": {"title_en": "Order under section 408A(2) to vacate / demolish / restore Corporation land", "title_hi": "धारा 408A(2) के अंतर्गत निगम भूमि खाली / ध्वस्त / पुनर्स्थापित करने का आदेश", "statute": HMCA, "section": "408A(2)", "kind": "ORDER", "min_days": 7, "default_days": 7, "template": "order_408a.html", "appeal_days": 7, "appeal_to": "Commissioner, Municipal Corporation Gurugram"},
    "DEMOLITION_ORDER_284": {"title_en": "Demolition Order under section 284(3) (unfit building)", "title_hi": "धारा 284(3) के अंतर्गत ध्वस्तीकरण आदेश", "statute": HMCA, "section": "284", "kind": "ORDER", "min_days": 30, "default_days": 30, "template": "order_demolition_284.html"},
    "DANGEROUS_BUILDING_ORDER_265": {"title_en": "Order under section 265(2) to demolish / secure / repair dangerous building", "title_hi": "धारा 265(2) के अंतर्गत खतरनाक भवन को ध्वस्त / सुरक्षित / मरम्मत करने का आदेश", "statute": HMCA, "section": "265(2)-(6)", "kind": "ORDER", "min_days": 0, "default_days": 7, "template": "order_265_2.html"},
    "VACATE_ORDER_266": {"title_en": "Order under section 266(1) to vacate building", "title_hi": "धारा 266(1) के अंतर्गत भवन खाली करने का आदेश", "statute": HMCA, "section": "266", "kind": "ORDER", "min_days": 0, "default_days": 7, "template": "order_vacate_266.html"},
    "IMMEDIATE_ACTION_265_4": {"title_en": "Memo of immediate action under section 265(4) (imminent danger)", "title_hi": "धारा 265(4) के अंतर्गत तत्काल कार्रवाई ज्ञापन", "statute": HMCA, "section": "265(2)-(6)", "kind": "MEMO", "min_days": 0, "default_days": 0, "template": "memo_265_4.html"},
    "SUMMARY_REMOVAL_240": {"title_en": "Summary removal memo under section 240 / 243(3)", "title_hi": "धारा 240 / 243(3) के अंतर्गत सारांश हटाव ज्ञापन", "statute": HMCA, "section": "240", "kind": "MEMO", "min_days": 0, "default_days": 0, "template": "memo_240.html"},
    "POLICE_REQUISITION_262_2": {"title_en": "Requisition to Police under section 262(2)", "title_hi": "धारा 262(2) के अंतर्गत पुलिस को अधियाचन", "statute": HMCA, "section": "262(2)", "kind": "MEMO", "min_days": 0, "default_days": 0, "template": "memo_police_262_2.html"},
    "WATCH_DEPUTATION_262_3": {"title_en": "Order deputing watch under section 262(3)", "title_hi": "धारा 262(3) के अंतर्गत निगरानी हेतु प्रतिनियुक्ति आदेश", "statute": HMCA, "section": "262(3)", "kind": "MEMO", "min_days": 0, "default_days": 0, "template": "memo_watch_262_3.html"},
    "OC_REVOCATION_HBC_4_12": {"title_en": "Order revoking Occupation Certificate (HBC 2017 Code 4.12)", "title_hi": "अधिभोग प्रमाण-पत्र निरस्तीकरण आदेश (एच.बी.सी. 2017 कोड 4.12)", "statute": HBC, "section": "4.12", "kind": "ORDER", "min_days": 0, "default_days": 0, "template": "order_oc_revocation.html"},
    "REFERRAL_TO_COLLECTOR_HPPA": {"title_en": "Referral to the Collector for eviction under sections 4-5 of the HPP Act, 1972", "title_hi": "एच.पी.पी. अधिनियम 1972 की धारा 4-5 के अंतर्गत बेदखली हेतु कलेक्टर को संदर्भ", "statute": HPPA, "section": "4", "kind": "REFERRAL", "min_days": 0, "default_days": 0, "template": "referral_collector.html"},
    "REFERRAL_TO_DTCP": {"title_en": "Referral to District Town Planner (Enforcement) under the 1963 Act", "title_hi": "1963 अधिनियम के अंतर्गत जिला नगर योजनाकार (प्रवर्तन) को संदर्भ", "statute": PSRCA, "section": "12(2)-(3)", "kind": "REFERRAL", "min_days": 0, "default_days": 0, "template": "referral_dtcp.html"},
    "EXECUTION_BY_CORPORATION": {"title_en": "Execution memo - demolition / sealing carried out by the Corporation (s.261(6) / 408A(3) / 263A(2)(c))", "title_hi": "निष्पादन ज्ञापन - निगम द्वारा ध्वस्तीकरण / सीलिंग", "statute": HMCA, "section": "261(6)", "kind": "MEMO", "min_days": 0, "default_days": 0, "template": "memo_execution.html"},
    "COST_RECOVERY": {"title_en": "Demand for recovery of demolition cost as arrears of tax / land revenue", "title_hi": "ध्वस्तीकरण लागत की कर / भू-राजस्व के बकाया के रूप में वसूली हेतु माँग", "statute": HMCA, "section": "261(6)", "kind": "MEMO", "min_days": 0, "default_days": 30, "template": "memo_cost_recovery.html"},
    "PROSECUTION_380": {"title_en": "Complaint for prosecution under section 380 / 386", "title_hi": "धारा 380 / 386 के अंतर्गत अभियोजन हेतु शिकायत", "statute": HMCA, "section": "380", "kind": "MEMO", "min_days": 0, "default_days": 0, "template": "memo_prosecution.html"},
    "POLICE_COMPLAINT": {"title_en": "Complaint to Police (BNS 2023 / obstruction / seal breach)", "title_hi": "पुलिस को शिकायत", "statute": BNS, "section": "223", "kind": "MEMO", "min_days": 0, "default_days": 0, "template": "memo_police_complaint.html"},
    "RE_AFFIXATION": {"title_en": "Re-affixation memo (s.407)", "title_hi": "पुनः चस्पा ज्ञापन (धारा 407)", "statute": HMCA, "section": "407", "kind": "MEMO", "min_days": 0, "default_days": 0, "template": "memo_reaffix.html"},
}

meta = {
    "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "generator": "shared/legal/generate_catalogue.py",
    "disclaimer": "Statutory text was extracted from scanned PDFs and cleaned by hand. Records marked verify=true must be checked against the official Gazette by the Legal Branch of MCG before the notices are used in court proceedings.",
}

with open(os.path.join(HERE, "legal_sections.json"), "w", encoding="utf-8") as f:
    json.dump({"meta": meta, "statutes": statutes, "sections": sections}, f, ensure_ascii=False, indent=2)
with open(os.path.join(HERE, "violation_catalogue.json"), "w", encoding="utf-8") as f:
    json.dump({"meta": meta, "categories": {
        GL: {"en": "Construction / encroachment on Government or Corporation land", "hi": "सरकारी / निगम भूमि पर निर्माण / अतिक्रमण"},
        PL: {"en": "Unauthorised construction on private land (no sanction)", "hi": "निजी भूमि पर अनधिकृत निर्माण (बिना स्वीकृति)"},
        DEV: {"en": "Deviation from sanctioned building plan", "hi": "स्वीकृत भवन योजना से विचलन"},
        ST: {"en": "Encroachment on streets / footpaths", "hi": "सड़क / फुटपाथ पर अतिक्रमण"},
        MIS: {"en": "Misuse / change of use / occupation without OC", "hi": "दुरुपयोग / उपयोग परिवर्तन / ओ.सी. के बिना अधिभोग"},
        DAN: {"en": "Dangerous / unfit buildings", "hi": "खतरनाक / अनुपयुक्त भवन"},
        PROC: {"en": "Non-compliance with notices and orders", "hi": "नोटिस और आदेशों का पालन न करना"},
    }, "order_types": order_types, "violations": violations}, f, ensure_ascii=False, indent=2)

# quick integrity check: every legal_basis must exist in sections
index = {(s["statute"], s["section"]) for s in sections}
missing = sorted({(b["statute"], b["section"]) for vi in violations for b in vi["legal_basis"]} - index)
print(f"sections={len(sections)} violations={len(violations)} order_types={len(order_types)}")
print("legal_basis references not found as section records (add them or accept as cross-references):", missing)
