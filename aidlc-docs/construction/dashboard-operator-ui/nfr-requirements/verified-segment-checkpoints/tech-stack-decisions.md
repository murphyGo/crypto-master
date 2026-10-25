# Technology Baseline

Retain project Python/Pydantic, existing canonical models/readers and original
Fly/Streamlit/CLI providers. Proposed internal work uses standard-library bounded
IO, generators, synchronization and JSON-compatible codecs. No new external
service, credential, database package, VM, mount or paid capacity is selected.
Raw pickle/executable cache data is excluded. Detailed worker/storage choices
remain NFR Design candidates; they are not active infrastructure changes.
