# TSC Materials for TESSIA

This directory contains the meeting notes, process documentations, and other materials related to this project.

## Project Intake checklist

This is a checklist for TSC's to review as part of the intake process. The TSC should review this entire list during the kickoff meeting. For anything outstanding, create an [issue](../issues) to track and link to it in the list

- TSC Record Keeping
  - [x] Location for TSC documents and meeting notes ( recommendation is ```tsc``` directory in main repo, and then ```meetings``` under the ```tsc``` directory )
  - [x] Copy this checklist to the above location for tracking
- Existing Project Governance
  - [x] README.md file exists ( example at [example_readme.md](example_readme.md) )
  - [x] Project License exists ( LICENSE.md ) and aligned with the [Open Mainframe Project IP Policy](https://github.com/openmainframeproject/foundation/blob/master/CHARTER.md#12-intellectual-property-policy)
  - [x] Any third-party components/dependencies included are listed along with thier licenses ( THIRD_PARTY.md )
  - [x] Governance defined, outlining community roles and how decsions are made ( GOVERNANCE.md - leverage [example_governance.md](example_governance.md) as a starting point if needed )
  - [x] Contribution Policy defined ( CONTRIBUTING.md )
  - [ ] Code of Conduct defined ( CODE_OF_CONDUCT.md - use existing or leverage [code of conduct](code_of_conduct.md) )
  - [x] Release methodology defined ( RELEASE.md )
- New Project Governance
  - [ ] TSC members identified
  - [ ] First TSC meeting held
  - [ ] TSC meeting cadence set and added to project calendar
- Current tools
  - [x] Source Control (Github, GitLab, something else )	
	- [ ] Issue/feature tracker (JIRA, GitHub issues)	
  - Collaboration tools 
    - [x] Mailing lists
      - [x] Move to groups.io ( create [issue on foundation repo] to setup/transfer )
    - [ ] Slack or IRC ( create [issue on foundation repo] to setup project channel on [OMP Slack](https://slack.openmainframeproject.org) )
    - [ ] Forums
  - [ ] Website
  - [x] CI/build environment	
- Project assets
  - [ ] Domain name	( create [issue on foundation repo] to setup/transfer
	- [ ] Social media accounts	( create [issue on foundation repo] to setup/transfer
	- [ ] Logo(s)	( create pull request [against artwork repo](https://github.com/openmainframeproject/artwork) to add in SVG and PNG format and color/black/white )
	- [ ] Trademarks/mark ownership rights ( complete [LF Projects - Form of Trademark and Account Assignment](lf_projects_trademark_assignment.md) )
- Outreach
  - [ ] New project announcement done ( create [issue on foundation repo] to trigger )
  - [ ] Project added to Open Mainframe Project website and Open Mainframe Project landscape
- Graduation
  - [ ] CII Badge achieved ( apply at https://bestpractices.coreinfrastructure.org/en )
  - [ ] Committer Diversity established
  	- [ ] Add project to [OMP Dev Anayltics](https://lfanalytics.io/projects/open-mainframe-project) ( create [issue on foundation repo] to trigger )
	- [ ] Commit/Contribution growth during incubation
	- [ ] Committers defined in the project	( [COMMITTERS.csv](COMMITTERS.csv) or [COMMITTERS.yml](COMMITTERS.yml) )
  - [ ] TAC representative appointed
  - [ ]	License scan completed and no issues found
  - [ ] Code repository imported to Open Mainframe Project GitHub organization
    - [ ] Developer Certificate of Origin past commit signoff done and DCO Probot enabled.


[issue on foundation repo]: https://github.com/openmainframeproject/foundation/issues/new/choose
