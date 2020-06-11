# Changelog for Thoth's micropipenv

## [0.3.0] - 2020-Jun-12 - Fridolin Pokorny <fridolin@redhat.com>

### Added

* Added support for pip in version >=19.2<20
* Introduced NotSupportedError exception raised when Mercurial, Subversion or
  Bazaar VCS are used
* Optimized traversals when requirements file is looked up
* Improvements in test-suite, now testing support matrix
  thanks to Lumir 'Frenzy' Balhar <lbalhar@redhat.com>

## [0.2.1] - 2020-Jun-9 - Fridolin Pokorny <fridolin@redhat.com>

### Fixes

* Fixed priority in lock files discovered
  thanks to Lumir 'Frenzy' Balhar <lbalhar@redhat.com>

### Docs

* Improved project documentation

## [0.2.0] - 2020-Jun-4 - Fridolin Pokorny <fridolin@redhat.com>

### Fixes
* Fixed automatic selection of desired installation method (not backwards
  compatible change, might break installations)

### Other

* Improved test suite, the test suite now considers a matrix of Python
  interpreter versions and different pip versions
* Relicensed to LGPL 3+

### Added

* Added support for pip in version 20

## [0.0.0] - 2020-Feb-10 - Fridolin Pokorny <fridolin@redhat.com>

### Added

Initial project import
