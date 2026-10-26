"""Local AppTest fixture: dispatch real saved Streamlit fragment closures."""
import streamlit as st
from streamlit.runtime.scriptrunner import get_script_run_ctx

from src.dashboard import availability

if st.session_state.get('dispatch_saved', False):
    st.session_state.dispatch_saved = False
    st.session_state.fragment_dispatches += 1
    st.session_state.saved_fragment()
    # A fired one-shot probe returns here; a new ready probe causes st.rerun.
    st.session_state.dispatches_that_returned += 1


@availability.watch_loading
def render():
    st.session_state.renders += 1
    result = st.session_state.service.request(st.session_state.query, wait=0)
    st.session_state.read_status = result.status
    if availability.show_availability(result, 'Activity'):
        st.metric('Ready', result.data()['value'])


render()
context = get_script_run_ctx()
assert context is not None
st.session_state.fragment_count = len(context.new_fragment_ids)
if context.new_fragment_ids:
    assert len(context.new_fragment_ids) == 1
    fragment_id = next(iter(context.new_fragment_ids))
    # Only save a newly registered real closure, not a previously dispatched
    # closure that was recorded in this new runner's ids but is not in storage.
    if context.fragment_storage.contains(fragment_id):
        st.session_state.saved_fragment = context.fragment_storage.get(fragment_id)
