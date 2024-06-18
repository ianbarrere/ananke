# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.4.0] - 2024-06-18

### Fixed

- Fixed local repo to present files in relative path format similar to GitLab

## [1.3.0] - 2024-06-12

### Fixed

- Behavior for targets all in dispatch. Still need to fix for when all and specific are
  updated.
- Removed unnecessary imports

### Changed

- Update repo_devices and repo_roles to look for directories that only have .yaml files
  as well (for devices in process of onboarding)
- Clear content_map after commit to avoid duplicate commit attempts
- Use non-j2 YAML for vars.yaml files

## [1.2.0] - 2024-05-16

### Fixed

- Get config wasn't working for some structures, this fix addresses that
- Better error handling of missed module imports

### Changed

- Big refactor of config_api, replaces RepoInterface and NetworkConfig with
  RepoConfigInterface, streamlines behavior and functionality of this construct and allows
  for better usability within the tooling code.

## [1.1.1] - 2024-04-29

### Changed

- Return Path object for list_objects() method of LocalRepo (GitLabRepo already does)

## [1.1.0] - 2024-04-25

### Changed

- Added better support for interfaces defined per file (now required due to changes in
  config repository needed to support NXOS better)
- A few cleanup things (documentation, variable renaming, unused imports, etc)

## [1.0.0] - 2024-04-15

### Changed

- Rewrote dispatch to be simpler and thread-based

## [0.3.4] - 2024-04-12

### Fixed

- Moved disable-set detection further down to allow dry-runs to display

## [0.3.3] - 2024-04-10

### Fixed

- Removed unnecessary variable from shared connector class
- Fixed variable reference in disable-set logic

## [0.3.2] - 2024-04-09

### Fixed

- Fixed incorrect empty target input

## [0.3.1] - 2024-04-09

### Fixed

- Restored all target functionality
- Fixed missing original content definition

## [0.3.0] - 2024-04-09

### Added

- Added diff_branches to LocalRepo

## [0.2.0] - 2024-03-14

### Added

- Added support for services

## [0.1.0] - 2023-12-25

### Added

- Added CHANGELOG.md
- Added pyproject.toml
- Added typed.py

[1.3.0]: https://gitlab.com/doubleverify/techops/sre/dv_sre_lib/-/tags/v1.2.0..v1.3.0
[1.2.0]: https://gitlab.com/doubleverify/techops/sre/dv_sre_lib/-/tags/v1.1.1..v1.2.0
[1.1.1]: https://gitlab.com/doubleverify/techops/sre/dv_sre_lib/-/tags/v1.1.0..v1.1.1
[1.1.0]: https://gitlab.com/doubleverify/techops/sre/dv_sre_lib/-/tags/v1.0.0..v1.1.0
[1.0.0]: https://gitlab.com/doubleverify/techops/sre/dv_sre_lib/-/tags/v0.3.4..v1.0.0
[0.3.4]: https://gitlab.com/doubleverify/techops/sre/dv_sre_lib/-/tags/v0.3.3..v0.3.4
[0.3.3]: https://gitlab.com/doubleverify/techops/sre/dv_sre_lib/-/tags/v0.3.2..v0.3.3
[0.3.2]: https://gitlab.com/doubleverify/techops/sre/dv_sre_lib/-/tags/v0.3.1..v0.3.2
[0.3.1]: https://gitlab.com/doubleverify/techops/sre/dv_sre_lib/-/tags/v0.3.0..v0.3.1
[0.3.0]: https://gitlab.com/doubleverify/techops/sre/dv_sre_lib/-/tags/v0.2.0..v0.3.0
[0.2.0]: https://gitlab.com/doubleverify/techops/sre/dv_sre_lib/-/tags/v0.1.0..v0.2.0
[0.1.0]: https://gitlab.com/doubleverify/techops/sre/dv_sre_lib/-/tags/v0.1.0