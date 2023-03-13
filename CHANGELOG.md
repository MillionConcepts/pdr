## [0.7.4] - 2023-03-13
### Added
 - support for a variety of LRO Diviner, Cassini, and Huygens data products    
   (see [supported_datasets.md](https://github.com/MillionConcepts/pdr/blob/main/supported_datasets.md) 
   for specifics)
 - This change log file
 - Support for bit columns with ITEMS
 - Browse images can now be output in grayscale
 - handling for COMPRESSED_FILE objects 

### Changed
 - pdr will now accept non-UTF-8 characters in detached PVL label / format files
 - refactored special case checking for readability/maintainability
 - assorted linting and in-code documentation edits
 - labels will by default read in up to 1 MB of the file (previously 500 bytes). If 
   you're trying to get faster performance for shorter attached labels en masse, pass 
   the new --pvl_limit parameter. If you're not running large numbers of attached 
   label files in sequence this is largely irrelevant.

### Fixed
 - label comments that are left unclosed by the data providers no longer prevent 
   reading in the data
 - group offset computations by offset not start byte (allows opening of Juno Jane V04 
   products, closes [issue 43](https://github.com/MillionConcepts/pdr/issues/43))
 - bit columns are now split based on both start_bit and number of bits rather than
   simply start_bit (this fixed a number of previously incorrectly read files, 
   and mirrors handling for other column types)
 - `dump_browse` now properly accepts the `float_dtype` argument; reducing
   bit depth can significantly reduce memory use when browsifying large arrays
 - malformed labels with extra end-block statements no longer crash `BlockParser`
 - JUNO JIRAM RDR special case now covers tables as well as images
 - HEADER objects in compressed files now load properly
 - DATA_SET_MAP_PROJECTION_CATALOGS no longer go to read_header (which does
   not work on them)

### Removed
 - special-case handling for COMPRESSED_FILEs
 - support for MSL CCAM LIBS EDRs
 

## [0.7.3] - 2023-01-18
### Added
 - Array pointers are now supported
 - FITS headers are now supported. (If a pointer with HEADER in it points to a FITS
   file it will return that header. If there is a pointer without HEADER in it that 
   points to the FITS file then after loading that key, an additional key will appear 
   in the format: `{key}_HEADER` that will contain the FITS header).
 - JPEG2000 (`.jp2`) files are now supported
 - Many new datatypes from missions including MGS, Clementine, Rosetta, and more
   (see [supported_datasets.md](https://github.com/MillionConcepts/pdr/blob/main/supported_datasets.md) 
   for specifics)

### Changed
 - Browse product improvements:
   - Tables with a single row of data will now output as a column for their .csv
     browse products to increase readability
   - Browse images can be specified to output in formats other than .jpg
 - `supported_datasets.md` is now alphabetically organized by mission name to more
   easily search
 - Various optimizations

### Fixed
 - Various bug fixes

## [0.7.2] - 2022-10-31
### Added
 - better search functionality for format files (description of behavior/usage can be found 
   [here](https://github.com/MillionConcepts/pdr/issues/36#issuecomment-1276764335))
 - A pretty printer for label metadata is now available. (Use print(data.metadata) to see the
   nicely formatted label information)
 - Image data with different scales and offsets can now be used with the browse products 
   created by `get_scaled`
 - Support was added for several Juno datasets (see supported_datasets.md for specifics).

### Changed
 - Accelerated bit handling (files with bit columns will now be processed faster).

### Fixed
 - Improvements for the position of column breaks in ASCII tables. Tables that were previously
   breaking the columns incorrectly will now behave correctly.

### Removed
 - `.jp2` files will not open with this release (full support planned for next release; small
 `.jp2` files will open with prior releases, but larger ones were not supported)

## [0.7.1] - 2022-09-28
### Added
 - Assorted compatibility extensions
### Fixed
 - Assorted bug fixes

## [0.7.0] - 2022-07-28
### Added
 - Full support for several previously notionally supported products

### Changed
 - A new unified interface for pds4-tools (the output of a pds4 file and a pds3 file
   will now be significantly more similar and the objects will behave the same)

## [0.6.3] - 2022-07-14
### Fixed
 - Added a quick patch to better discern if a table should be interpreted as binary or
   ascii

## [0.6.2] - 2022-06-27
### Fixed
 - Bug fixes for table reading due to signature change in dustgoggles

## [0.6.1] - 2022-06-01
### Added
 - Initial reference release

## Versions not released:
### [0.6.0] - 2022-04-13

Versioning becomes consistent at this point (prior to this release the version
number in setup.py followed a `0.4.#a` convention while the version in `__init__.py` follows
a `0.#.0` convention. Due to this the version numbers are enumerated here but are not mutually
exclusive).

### [0.5.0] - 2021-12-01

### [0.4.3a] - 2021-07-23

### [0.4.2a] - 2021-02-07
This version number is in both `__init__.py` and setup.py until setup.py changes to 0.4.3a

### [0.2.0] - 2021-01-28
This is a substantial rewrite of the core module. It generalizes the handling 
of common data object types, especially images and tables. The returned data object 
can now be treated somewhat like a dict by invoking the keys() method or using
`__getitem__` behavior, which should make it easier to use generally. It also addresses 
[issue #6](https://github.com/MillionConcepts/pdr/issues/6).

### [0.4a1] - 2020-12-31
`setup.py` is created and the package is made installable

### [0.1.0] - 2020-05-24
