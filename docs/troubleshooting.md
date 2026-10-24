# Local runtime recipe troubleshooting

For a supported alternative to this unsupported recipe, use CrossOver.
The README links to CodeWeavers and the historical Porting Kit Steam recipe.

## Export rejected

`tools/runtime_recipe.py` writes an explicit error to stderr and exits 1
without writing a registry to stdout when input validation fails.
Do not pass an empty output file to Ode after a failed export.

Use an absolute path to the existing Ode engine registry and its exact
engine name. A recipe is not a separate Calimocho engine. Duplicate names,
duplicate JSON keys, missing paths, unsupported schema, and changed file
hashes require correcting or re-admitting the upstream registry through
its existing tooling. The exporter never repairs or downloads a runtime.

An entrypoint must resolve inside its declared installation. Its environment
must not redirect Wine or wineserver elsewhere or preselect a prefix.
Do not fix an error by copying CrossOver binaries, applying the retired
Calimocho shim defaults, disabling trust checks, or substituting another
engine without an explicit selection.

## Export succeeded but the game is not qualified

Export success means only that the selected record could be represented and
its checked local references matched at export time. Directory dependency
contents and all historical receipt claims are not independently verified.
The existing Ode adapter must re-admit the exact route and enforce prefix
ownership when launching. Never infer main-menu, gameplay, or save reload
success from the presence of Wine or renderer files.

The archived Subnautica 2 Steam recipe is not Xbox compatibility evidence.
No game launch, prefix mutation, security-setting change, release, or
redistribution is authorized by creating an export.
