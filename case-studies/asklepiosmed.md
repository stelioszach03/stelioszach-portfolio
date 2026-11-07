# AsklepiosMed — Applied AI and a production association platform

**Former Head Engineer · June 2022–July 2026 · Pro bono**

[Public website](https://asklepiosmed.org/) · [Portfolio overview](https://stelioszach.com/#asklepios)

I worked as Head Engineer for the Paphos Medical Association from June 2022 to July 2026, pro bono, and developed and donated AsklepiosMed to support its member services and administrative work. My role ended in July 2026.

The project has continued to evolve. The sections below describe its current capabilities and architecture, including development after my tenure. The platform now combines a public website, a member portal, secretariat workflows and a separate engineering view.

This is a public engineering case study. Application source, operational configuration and member records remain private.

## Engineering ownership

I owned the React/Express/PostgreSQL implementation and Linux deployment, translating member and secretariat workflows into a maintained application. The delivered system brings publishing, member access, events and administrative work into one platform. Current AI capabilities extend that workflow with content drafting, editing and multilingual publication. The dated pro bono role and subsequent project development remain distinct.

## The problem

A professional association needs to publish information, support its members, organise events and handle sensitive requests without turning each workflow into a separate manual process. Those tasks also require different access boundaries: members should see their own records, the secretariat should manage its assigned work, and engineering access should not automatically reveal confidential case content.

## Applied AI and multilingual NLP

I built AI-assisted communication workflows into the platform's administrative publishing experience: administrators can turn notes into structured announcements, prepare email drafts, proofread existing copy and improve its wording. Drafting, proofreading and rewriting remain distinct operations, so the interface can communicate the scope of an edit.

The multilingual pipeline translates Greek announcements and articles into **English, Russian and Simplified Chinese**. It processes complete rich-text passages, with domain terminology and protected names carried into the target language. The implementation checks required fields, protected terms, suspicious content loss and HTML structure, and falls back to the existing translation service when an LLM response fails validation.

The engineering work includes structured JSON responses, output sanitization, content-integrity checks, shared token-usage accounting, bounded retries and explicit failure states. Editors review the suggestions in the publishing workflow. These are implemented application controls; no unmeasured translation-accuracy score or guarantee of factual preservation is claimed.

These capabilities describe the current project, including development after the June 2022–July 2026 pro bono role. They are LLM application engineering and multilingual NLP integration, not a claim of training or fine-tuning a foundation model. No private source or member content is published here.

## Current project capabilities

| Area                          | Implemented workflows                                                                                                             |
| ----------------------------- | --------------------------------------------------------------------------------------------------------------------------------- |
| AI and multilingual content | Announcement and email preparation, proofreading, rewriting and Greek-to-English/Russian/Simplified Chinese translation |
| Member access                 | Activation, mandatory profile review, verified contact-change flows, passkeys and recovery paths                                  |
| Information and communication | Public articles and announcements, member notifications and explicit communication preferences                                    |
| Secretariat publishing        | Private content drafts, preview, publication, revision restore and publication-conflict handling                                  |
| Events and learning           | Meeting invitations, conference participation, attendance records and issued participation certificates                           |
| Membership credentials        | Apple/Google Wallet membership cards with public status verification; membership verification is not medical-licence verification |
| Confidential casework         | Member submissions, encrypted attachments, assigned-secretariat access, messages, status history and linked requests for review   |
| Operations                    | Service monitoring, encrypted backups, restoration checks and documented recovery procedures                                      |

## Engineering approach

The application uses React, Express and PostgreSQL, with nginx and systemd on a VPS. Work spans the interface, API behaviour and the operational procedures needed to maintain a running service.

```mermaid
flowchart LR
  Public[Public website] --> Edge[HTTPS / nginx]
  Member[Member portal] --> Edge
  Staff[Secretariat workspace] --> Edge
  Engineer[Engineering view] --> Edge
  Edge --> API[Express API / scoped authentication]
  API --> Roles[Ownership and assignment checks]
  Roles --> DB[(PostgreSQL)]
  Roles --> Files[Protected attachments]
  API --> Jobs[Communication and event workflows]
  API --> AI[AI-assisted writing and translation]
  AI --> Checks[Structured output and integrity checks]
  Checks --> Review[Editor review and publication]
  DB --> Backup[Encrypted backups / restore checks]
  API --> Ops[Service health / operational logs]
```

This is a logical view of the single-VPS application. Separate boxes describe responsibilities, not independent fault-tolerant machines. Member ownership and secretariat assignment govern confidential case access; the engineering view is not a blanket permission to read case content.

Security-sensitive operations use scoped authentication checks. Confidential case access is limited by ownership and assignment, rather than treating every administrator as entitled to read everything. Content publication handles competing edits, and communication workflows make consent, review and explicit approval visible.

Verification has included focused automated tests, synthetic end-to-end workflows, responsive browser checks and backup restoration exercises. These are practical checks of particular behaviours, not a claim that software can be proved bug-free.

## Outcome and evidence

The public website and documented member/administrative workflows form the delivered software artifact. This case study does not claim measured adoption, staff time saved, security certification or a clinical outcome: no independently audited figures for those outcomes are published here. Operational records, private screenshots and member data are not used as portfolio material.

## Boundaries

- This is professional-association software, not a clinical decision system or patient electronic-health-record platform.
- The deployment uses a single VPS; it is not a highly available multi-region architecture.
- Selected sensitive records and backups are encrypted. That does not mean whole-disk or end-to-end encryption of every datum.
- A Wallet membership result does not authenticate the physical holder or certify a medical licence. Native NFC and an independently verified native iOS application are not claimed.
- A linked request for review supports a workflow; it does not establish statutory disciplinary or appeals authority.
- Technical privacy controls do not constitute a GDPR certification. Governance and retention decisions remain responsibilities of the association.

The [public platform](https://asklepiosmed.org/) can be viewed without access to member records. No private credentials, member data or production configuration are included in this portfolio repository.
