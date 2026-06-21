# Large Drive Scanning Strategy

## Problem
Founding deep scans on Drives with 10K+ items (50K+ in this case) exceed the 10-minute cron timeout when attempting full enumeration.

## Symptoms
- `bower.scan.deep` runs for 5+ minutes just listing items
- Background process killed at 10-minute timeout
- Google Drive API returns 500 Internal Errors under load
- Folder-only queries still paginate through thousands of folders

## Solution: Sampled Deep Scan

For Drives with >10K estimated items, use a **sampled deep scan** instead of full enumeration:

### Sampling Strategy
1. **Root level**: Full enumeration (files + folders at Drive root)
2. **Per root folder**: Sample up to 300 files (3 pages × 100) per top-level folder
3. **Subfolders**: Count only (no file enumeration)
4. **Content reading**: Only for sampled Google Docs/Sheets/Slides

### Time Budget
- Root listing: ~15 seconds
- 19 root folders × 3 pages × 100 files: ~3-5 minutes
- Content reading (371 files): ~1-2 minutes
- Analysis & proposals: ~30 seconds
- **Total: ~5-7 minutes** (within 10-min cron limit)

### Trade-offs
| Aspect | Full Enumeration | Sampled Scan |
|--------|------------------|--------------|
| File coverage | 100% | ~20-50% |
| Domain detection | Complete | Root-level only |
| Proposal depth | All files | Root-level + sampled |
| Scan coverage field | 1.0 | 0.5 |
| Follow-up | None needed | Weekly deep scan fills gaps |

### Implementation Notes
- Set `scan_coverage: 0.5` in `drive_digest.json`
- Add `scan_notes` documenting the sampling approach
- Weekly deep scan (`bower:weekly-deep`) will run full enumeration
- Proposals focus on root-level outliers and domain-prescriptive moves

## 500 Error Handling
Google Drive API returns 500 Internal Errors intermittently during heavy pagination. Always wrap list calls with exponential backoff:

```python
for attempt in range(3):
    try:
        r = drive.files().list(...).execute()
        break
    except HttpError as e:
        if e.resp.status in (500, 503) and attempt < 2:
            time.sleep(2 ** attempt)
        else:
            raise
```

## When to Use Sampled Scan
- Founding run on Drive with >10K items (check via `about.get` storage or quick root count)
- Any deep scan that exceeds 5 minutes on folder enumeration
- Cron jobs with strict time limits

## Future Enhancement
Consider adding a `--sample` flag to `bower.scan.deep` that automatically switches to sampled mode based on item count estimates.