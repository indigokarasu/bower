# Changelog

## [1.0.1] - 2026-03-30

### Added
- `## Ontology types` section per authoring rules v2.4.0 (Thing/DigitalArtifact declared)


## [1.0.0] - 2026-03-30

### Added
- Initial release of Bower
- Deep scan (`bower.scan.deep`) with content reading, description generation, and checkpoint/resume
- Light scan (`bower.scan.light`) with drift detection and arrival detection
- Analysis engine (`bower.analyze`) with domain-specific and generic outlier logic
- Simulation mode (`bower.simulate`) for read-only previews
- Proposal lifecycle: generate, review, approve, apply, undo
- Founding run (`--founding` flag) for one-time batch bootstrap with immediate pattern promotion
- Domain support: Taxes, Projects, Home, Finance, Legal, Medical, Archive, Education
- Prescriptive and descriptive mode selection per domain
- Preference profile inference: naming conventions, depth preference, sacred folders, domain detection
- Pattern promotion and auto-approval with demotion on undo/reject
- Feedback learning and proposal suppression
- Confidence recalibration per outlier class
- Permission safety: O(1) folder_index comparison blocks permission-changing moves
- Description auto-writes for empty fields; overwrite proposals for existing descriptions
- Rename proposals (high confidence only, five required conditions)
- Quiet mode for silent apply runs
- Apply cap (25 proposals) and describe_auto_cap (50 auto-writes) per run
- Proposal expiry (14-day default)
- Pre-apply staleness gate per proposal
- Weekly Drive health signal to Vesper intake
- Full audit trail: move_log, undo_log, feedback_log, scan_events, analysis_events
- Background tasks: daily light scan (2am PT), weekly deep scan (Sunday 1am PT)
