# Changelog for Thoth's micropipenv

## [1.0.2] - 2020-December-10 - Fridolin Pokorny <fridolin@redhat.com>

### Added

* Test with pip==20.3
* Test with pip==20.3.1

## [1.0.1] - 2020-November-09 - Fridolin Pokorny <fridolin@redhat.com>

### Added

* Make the installation log prettier
* Test with pip==20.2.4

## [1.0.0] - 2020-October-01 - Fridolin Pokorny <fridolin@redhat.com>

### Added

* First major release
* Tested with pip==20.2.3

## [0.6.0] - 2020-September-03 - Fridolin Pokorny <fridolin@redhat.com>

### Added

* Produce error message if any issue is raised during pip imports (#124)
* Produce pip compatibility warning only on issues (#121)
* Test micropipenv against pip from the master branch (#122)

### Other

* Drop Python 3.5 support (#128)

## [0.5.3] - 2020-August-18 - Fridolin Pokorny <fridolin@redhat.com>

### Added

* Test against pip==20.2.2

## [0.5.2] - 2020-August-05 - Fridolin Pokorny <fridolin@redhat.com>

### Added

* Test against pip==20.2.1

## [0.5.1] - 2020-Jul-30 - Fridolin Pokorny <fridolin@redhat.com>

### Added

* Improvements in the test suite for online tests and different environments
  setup

## [0.5.0] - 2020-Jul-23 - Fridolin Pokorny <fridolin@redhat.com>

### Added

* Add support for a direct reference install using Pipenv and requirements.txt file
  thanks to Tomáš Coufal <tcoufal@redhat.com> for Pipenv support

* More descriptive warning message in the unpinned warning message

## [0.4.0] - 2020-Jul-07 - Fridolin Pokorny <fridolin@redhat.com>

### Added

* Added pytoml support needed for Red Hat Enterprise Linux
  thanks to Lumir 'Frenzy' Balhar <lbalhar@redhat.com>

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
