# Mendeley Connector

**What it provides**
Access to a user's Mendeley library: document metadata, group libraries, and annotations, for pulling references into a manuscript's bibliography.

**Mechanism**
Docs-only. No programmatic integration is shipped; the fallback is manual export from Mendeley (BibTeX) and import into the manuscript library.

**Install and environment variables**
Nothing to install. To use Mendeley today, export the library (or a folder/group) as BibTeX from the Mendeley desktop app or web library, then import that file into `manuscript/references/library.bib`.

**Used by**
citation-management

**Fallback when absent**
citation-management skips automated Mendeley sync and instead prompts for a manually exported BibTeX file, validating entries via DOI lookup as usual.

**Data egress**
Core makes no call to Mendeley: nothing leaves through this plugin for it. The workflow is a manual BibTeX export you produce yourself in Mendeley and import into `manuscript/references/library.bib`, so no Mendeley network request is made by Researcher.

**Terms of use**
Documentation-only. No programmatic integration is shipped; your use of Mendeley is governed by Mendeley's own terms and privacy policy. See https://www.mendeley.com/ . Verified as of 2026-07-14; re-verify at release.
