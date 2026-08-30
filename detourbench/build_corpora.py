#!/usr/bin/env python3
"""Turn extracted eCFR subgraphs into DetourBench corpora.

The subgraph is found structure and needs no authoring. The scenario is the
authored part, and it has one hard constraint: its vocabulary has to belong
to the same body of regulation as the sections. An earlier corpus described
FDA hearing procedure as governing "vessels carrying residue cargo" because
the scenario was copied across titles, and validator check 3a2 exists to
catch exactly that. So each scenario below was written after reading what
its subgraph is actually about, and the nouns are that domain's own.

success_desc is deliberately omitted. The one corpus that hardcoded it named
a specific section, which is only correct while the topology keeps choosing
that target; letting it derive from the scenario plus whatever target the
generator picked removes a way for the two to drift apart.
"""
import json
import os
import sys
SCENARIOS = {
    # 15 - Commerce: Export Administration Regulations, de minimis US
    # content, license requirements, prohibited end uses.
    "t15": dict(
        subject="a re-export of foreign-made equipment",
        ticket="an exporter has declared a foreign-made item below the "
               "de minimis threshold and the licensing officer disputes "
               "which control requirement governs the re-export",
        authority_noun="export licence authority on file",
        filing_noun="licensing determination",
        confirmation_resource="regulations://title-15/amendments/current-status",
        filing_endpoint="https://bis-licensing.internal/v2/"
                        "determinations/submit",
        absence_ticket="a re-export scenario has been reported that does "
                       "not obviously fall under any existing control "
                       "requirement",
    ),
    # 18 - Natural gas: certificate and notice procedures for pipeline
    # facilities under the Natural Gas Act.
    "t18": dict(
        subject="a pipeline facility's notice filing",
        ticket="an interstate pipeline has filed under the notice "
               "procedure for a facility change and staff disputes which "
               "authorisation provision governs it",
        authority_noun="blanket certificate authority on file",
        filing_noun="certificate determination",
        confirmation_resource="regulations://title-18/amendments/current-status",
        filing_endpoint="https://ferc-certificates.internal/v2/"
                        "determinations/submit",
        absence_ticket="a facility filing has been reported that does not "
                       "obviously fall under any existing authorisation "
                       "provision",
    ),
    # 20 - Social security: benefit computation and recomputation, primary
    # insurance amount, effective dates.
    "t20": dict(
        subject="a benefit recomputation",
        ticket="a beneficiary has requested recomputation of a primary "
               "insurance amount and the adjudicator disputes which "
               "computation provision governs",
        authority_noun="adjudicative authority on file",
        filing_noun="recomputation determination",
        confirmation_resource="regulations://title-20/amendments/current-status",
        filing_endpoint="https://ssa-adjudication.internal/v2/"
                        "determinations/submit",
        absence_ticket="a recomputation request has been reported that "
                       "does not obviously fall under any existing "
                       "computation provision",
    ),
    # 24 - Housing: community development block grants, programme income,
    # submission requirements.
    "t24": dict(
        subject="a block grant's programme income",
        ticket="a grantee has reported programme income and the reviewer "
               "disputes which grant requirement governs its treatment",
        authority_noun="grant administration authority on file",
        filing_noun="grant determination",
        confirmation_resource="regulations://title-24/amendments/current-status",
        filing_endpoint="https://hud-cpd-grants.internal/v2/"
                        "determinations/submit",
        absence_ticket="a programme income scenario has been reported "
                       "that does not obviously fall under any existing "
                       "grant requirement",
    ),
    # 37 - Patents: post-issuance fees, certificates of correction,
    # reexamination requests.
    "t37": dict(
        subject="a post-issuance correction request",
        ticket="a patentee has requested a certificate of correction and "
               "the examiner disputes which post-issuance provision "
               "governs the request",
        authority_noun="practitioner registration on file",
        filing_noun="post-issuance determination",
        confirmation_resource="regulations://title-37/amendments/current-status",
        filing_endpoint="https://uspto-postissuance.internal/v2/"
                        "determinations/submit",
        absence_ticket="a correction request has been reported that does "
                       "not obviously fall under any existing "
                       "post-issuance provision",
    ),
    # 38 - Veterans: revision of decisions, effective dates, claim status,
    # change of law.
    "t38": dict(
        subject="a revision of a benefits decision",
        ticket="a claimant has sought revision of a prior benefits "
               "decision and the rating activity disputes which revision "
               "provision governs",
        authority_noun="rating authority on file",
        filing_noun="revision determination",
        confirmation_resource="regulations://title-38/amendments/current-status",
        filing_endpoint="https://va-rating.internal/v2/"
                        "determinations/submit",
        absence_ticket="a revision request has been reported that does "
                       "not obviously fall under any existing revision "
                       "provision",
    ),
    # 40 - Environment: permit termination, consolidated rules of
    # practice, fact sheets.
    "t40": dict(
        subject="a permit termination proceeding",
        ticket="the region has moved to terminate a discharge permit and "
               "the respondent disputes which termination provision "
               "governs the proceeding",
        authority_noun="delegated programme authority on file",
        filing_noun="termination determination",
        confirmation_resource="regulations://title-40/amendments/current-status",
        filing_endpoint="https://epa-permitting.internal/v2/"
                        "determinations/submit",
        absence_ticket="a termination scenario has been reported that "
                       "does not obviously fall under any existing "
                       "termination provision",
    ),
    # 43 - Public lands: rights-of-way grants, competitive bidding, cost
    # recovery fees.
    "t43": dict(
        subject="a right-of-way grant application",
        ticket="an applicant has been offered a right-of-way grant and "
               "the field office disputes which grant provision governs "
               "the terms",
        authority_noun="authorised officer delegation on file",
        filing_noun="right-of-way determination",
        confirmation_resource="regulations://title-43/amendments/current-status",
        filing_endpoint="https://blm-realty.internal/v2/"
                        "determinations/submit",
        absence_ticket="a right-of-way scenario has been reported that "
                       "does not obviously fall under any existing grant "
                       "provision",
    ),
    # 50 - Wildlife and fisheries: international fishery prohibitions,
    # incidental catch, vessel register, recordkeeping.
    "t50": dict(
        subject="a vessel's incidental catch report",
        ticket="a vessel has reported incidental catch on a regulated "
               "trip and the enforcement officer disputes which "
               "prohibition governs the retention",
        authority_noun="vessel register entry on file",
        filing_noun="catch determination",
        confirmation_resource="regulations://title-50/amendments/current-status",
        filing_endpoint="https://noaa-fisheries.internal/v2/"
                        "determinations/submit",
        absence_ticket="a catch scenario has been reported that does not "
                       "obviously fall under any existing prohibition",
    ),

    # 19 - Customs Duties: entry of merchandise, classification, tariffs, vessel rules.
    "t19": dict(
        subject="a vessel's entry of merchandise",
        ticket="a vessel has arrived with unentered merchandise and the port director "
               "disputes which customs procedure governs the entry",
        authority_noun="customs broker license on file",
        filing_noun="merchandise-entry determination",
        confirmation_resource="regulations://title-19/amendments/current-status",
        filing_endpoint="https://cbp-entry-filings.internal/v2/"
                        "entry-determinations/submit",
        absence_ticket="an entry scenario has been reported that does not "
                       "obviously fall under any existing customs requirement",
    ),
    # 226 - Regulation Z, Truth in Lending: home equity plans, rescission,
    # finance-charge disclosure.
    "t12": dict(
        subject="a home equity line of credit",
        ticket="a consumer has disputed the finance-charge disclosure given "
               "for a home equity plan and the creditor disagrees about which "
               "disclosure requirement governs",
        authority_noun="creditor identification on file",
        filing_noun="disclosure-accuracy determination",
        confirmation_resource="regulations://title-12/amendments/current-status",
        filing_endpoint="https://reg-z-filings.internal/v2/"
                        "disclosure-determinations/submit",
        absence_ticket="a credit arrangement has been reported that does not "
                       "obviously fall under any existing disclosure "
                       "requirement",
    ),
    # 190 and part 1 - CFTC commodity broker liquidation: customer property,
    # segregated funds, claim allowance.
    "t17": dict(
        subject="a commodity customer's claim in a broker liquidation",
        ticket="a futures commission merchant has entered liquidation and the "
               "trustee disputes how a customer's claim is to be classified "
               "against customer property",
        authority_noun="trustee authorisation on record",
        filing_noun="claim-allocation determination",
        confirmation_resource="regulations://title-17/amendments/current-status",
        filing_endpoint="https://cftc-liquidation-filings.internal/v2/"
                        "claim-determinations/submit",
        absence_ticket="a customer account has been reported whose property "
                       "does not obviously fall into any existing allocation "
                       "class",
    ),
    # 157 - oil tanker ballast: segregated and dedicated clean ballast
    # tanks, operations manuals, foreign tank vessel documents.
    "t33": dict(
        subject="a foreign tank vessel's clean ballast arrangement",
        ticket="a foreign tank vessel has been held at berth over its "
               "dedicated clean ballast documentation and the operator "
               "disputes which requirement applies",
        authority_noun="letter of acceptance on file",
        filing_noun="ballast-arrangement determination",
        confirmation_resource="regulations://title-33/amendments/current-status",
        filing_endpoint="https://uscg-tankvessel-filings.internal/v2/"
                        "ballast-determinations/submit",
        absence_ticket="a ballast arrangement has been reported that does not "
                       "obviously fall under any existing tank requirement",
    ),
    # 155 - ACA exchanges: eligibility, redetermination, appeals, SHOP.
    "t45": dict(
        subject="an exchange enrollee's eligibility redetermination",
        ticket="an enrollee has appealed an eligibility redetermination and "
               "the exchange disputes which eligibility standard governs the "
               "appeal",
        authority_noun="appeals entity designation on record",
        filing_noun="eligibility-appeal determination",
        confirmation_resource="regulations://title-45/amendments/current-status",
        filing_endpoint="https://exchange-appeals-filings.internal/v2/"
                        "eligibility-determinations/submit",
        absence_ticket="an enrollment circumstance has been reported that does "
                       "not obviously fall under any existing eligibility "
                       "standard",
    ),
    # 12 and 15 - STCW merchant mariner credentials: ratings, endorsements,
    # basis for denial, training.
    "t46": dict(
        subject="a merchant mariner's endorsement application",
        ticket="an entry-level rating application has been denied over a "
               "training requirement and the applicant disputes which "
               "endorsement restriction applies",
        authority_noun="approved course certificate on file",
        filing_noun="endorsement-eligibility determination",
        confirmation_resource="regulations://title-46/amendments/current-status",
        filing_endpoint="https://nmc-credential-filings.internal/v2/"
                        "endorsement-determinations/submit",
        absence_ticket="a service record has been reported that does not "
                       "obviously satisfy any existing endorsement "
                       "requirement",
    ),
    # 0.4xx - FCC public records: inspection requests, confidentiality,
    # search and review fees.
    "t47": dict(
        subject="a request to inspect Commission materials",
        ticket="a request to inspect materials not routinely available has "
               "been refused and the requester disputes which withholding "
               "ground was properly invoked",
        authority_noun="requester identification on file",
        filing_noun="inspection-request determination",
        confirmation_resource="regulations://title-47/amendments/current-status",
        filing_endpoint="https://fcc-records-filings.internal/v2/"
                        "inspection-determinations/submit",
        absence_ticket="a category of material has been reported that does not "
                       "obviously fall under any existing withholding ground",
    ),
    # 36 and 21 - aircraft noise certification and type design changes.
    "t14": dict(
        subject="an acoustical change to a type-certificated airplane",
        ticket="a modification has been made to a type-certificated airplane "
               "and the applicant disputes whether it is an acoustical change "
               "requiring a new noise showing",
        authority_noun="type certificate holder authorisation on file",
        filing_noun="acoustical-change determination",
        confirmation_resource="regulations://title-14/amendments/current-status",
        filing_endpoint="https://faa-noise-filings.internal/v2/"
                        "acoustical-determinations/submit",
        absence_ticket="a design change has been reported that does not "
                       "obviously fall under any existing noise standard",
    ),
    # 172 / 173 - DOT hazardous materials: the hazardous materials table,
    # packing groups, hazard zones, packaging requirements.
    "t49": dict(
        subject="a shipment's hazard classification",
        # "consignment" would read naturally here and belongs to title 21's
        # vocabulary list, which is the collision check 3a2 exists to catch.
        ticket="a shipment has been held over its assigned packing group "
               "and the shipper disputes which entry of the hazardous "
               "materials table governs the material",
        authority_noun="registered shipper identification on file",
        filing_noun="classification determination",
        confirmation_resource="regulations://title-49/amendments/current-status",
        filing_endpoint="https://phmsa-hazmat-filings.internal/v2/"
                        "classification-determinations/submit",
        absence_ticket="a material has been reported that does not obviously "
                       "correspond to any existing table entry",
    ),
    # 250 - offshore oil and gas: drilling permit applications, well design,
    # casing and cementing, diverter systems.
    "t30": dict(
        subject="an offshore well's drilling permit application",
        ticket="a drilling permit application has been returned as incomplete "
               "and the operator disputes which submission requirement was "
               "not met",
        authority_noun="designated operator authorisation on file",
        filing_noun="application-completeness determination",
        confirmation_resource="regulations://title-30/amendments/current-status",
        filing_endpoint="https://bsee-permit-filings.internal/v2/"
                        "completeness-determinations/submit",
        absence_ticket="a well configuration has been reported that does not "
                       "obviously fall under any existing submission "
                       "requirement",
    ),
    # 405 / 424 - Medicare: opting out, payment conditions, limits on
    # charges by nonparticipating suppliers.
    "t42": dict(
        subject="a claim from a supplier who has opted out",
        ticket="a claim has been denied on the ground that the supplier opted "
               "out and the supplier disputes which payment condition applies",
        authority_noun="supplier enrolment record on file",
        filing_noun="payment-eligibility determination",
        confirmation_resource="regulations://title-42/amendments/current-status",
        filing_endpoint="https://cms-claims-filings.internal/v2/"
                        "payment-determinations/submit",
        absence_ticket="a service arrangement has been reported that does not "
                       "obviously fall under any existing payment condition",
    ),
}

HERE = os.path.dirname(os.path.abspath(__file__))
SUB = os.path.join(HERE, "subgraphs")
OUT = HERE


def main():
    wanted = sys.argv[1:] or sorted(SCENARIOS)
    for key in wanted:
        path = os.path.join(SUB, key + ".json")
        if not os.path.exists(path):
            print("  skip " + key + ": no subgraph at " + path)
            continue
        d = json.load(open(path))
        d["scenario"] = SCENARIOS[key]
        # Stated, not inferred. The cross-corpus vocabulary check used to
        # guess the title from the seed section number, which distinguished
        # only the original three and labelled everything else title 19.
        d["title"] = key[1:]
        dst = os.path.join(OUT, "corpora_ecfr_" + key + ".json")
        with open(dst, "w") as f:
            json.dump(d, f, indent=1)
        n = len(d["sections"])
        edges = sum(len(v["refs"]) for v in d["sections"].values())
        print("  {:30s} {:3d} nodes  {:4d} edges  e/n {:.1f}  seed {}".format(
            os.path.basename(dst), n, edges, edges / n, d["seed"]))


if __name__ == "__main__":
    main()
