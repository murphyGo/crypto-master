# Implementation Summary: sub-account-experiment-marketplace

Initial code generation adds `ExperimentTemplate`, a frozen schema for reusable
sub-account experiments. Templates validate safe ids, quote currency, strategy
filter shape, and risk overrides, then materialise a normal `SubAccount`
without introducing a second runtime account model.

Templates now render copyable `sub_accounts` YAML fragments through
`render_sub_account_yaml_fragment`. The rendered fragment round-trips through
the existing `SubAccountRegistry` loader.
