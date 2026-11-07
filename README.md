# Bin Calendar Auto

Automatically publish Barking & Dagenham Council bin collections to a subscribed calendar with **6pm UK-time evening-before reminder events**.

## Setup

1. Under **Settings → Secrets and variables → Actions**, create a repository secret called **BIN_UPRN** containing the property UPRN from your original script. Don't commit a UPRN to this public repository.
   Also create **BIN_POSTCODE**, containing your full postcode (with space), for the fallback source if the council blocks GitHub with 403. The postcode is not placed in the calendar or committed. The fallback uses the independent UK Bin Day service (not operated by the council) and may not cover every property.
2. Under **Settings → Actions → General → Workflow permissions**, allow **Read and write permissions** where available.
3. Under **Actions → Update bin collection calendar → Run workflow**, run once with **force** enabled. The workflow runs tests, fetches the council dates, writes `docs/bin_collection_schedule.ics` and commits the update.
4. Under **Settings → Pages**, choose **Deploy from a branch**, branch **main**, folder **/docs**, and save.
5. After the first workflow and Pages build, subscribe in Google Calendar on desktop using **Other calendars → + → From URL**:
   `https://ekininj4x.github.io/bin-calendar-auto/bin_collection_schedule.ics`

Do **not** use Google Calendar's one-time Import option: use **From URL** so it can refresh. It controls how often it checks subscribed calendar URLs.

## Operation

- GitHub Actions checks every Monday at 07:23 UTC.
- The script refreshes when **21 days** have elapsed since the last successful update. You can force a refresh from GitHub Actions at any time.
- Each bin/date has a stable event identifier; duplicate dates from the API are removed.
- A **6pm local UK time** event the evening before lists the bins to put out. Its embedded alarm is best-effort: Google Calendar may not honour notification alarms from subscribed feeds. Configure the calendar's own event notifications where supported.
- Failed API calls and empty responses leave the previous published ICS untouched.
- A public Pages feed is accessible to anyone with the URL. It contains collection dates and bin names but not your property UPRN or address.
- A scheduled workflow may be delayed by GitHub; if GitHub disables it after inactivity, re-enable the workflow.

To test locally: `python -m unittest discover -s tests -v`. Python 3.12+; no third-party dependencies.
