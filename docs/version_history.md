# Version History

## [1.3.0] - 2024-10-18
### Added

#### Features
- `Data.dump_browse()` and `Data.show()` now take an optional `slice_axis`
  keyword argument which controls which axis of a 3-D image array `Data` 
  treats as the 'band' or 'channel' axis

#### Dataset Support
- MGS MOLA PEDR (a special case fixes non-standard STRUCTURE pointer names and
  'ROWS = "UNK"' from the labels)
- LRO LAMP EDR and most RDR table/image pointers
- additional IUE images 
- Apollo Lunar Sample Photographs

#### Other
- Our [JOSS paper](https://joss.theoj.org/papers/10.21105/joss.07256) was accepted for publication! :tada: A pdf of our JOSS 
  publication is included in the documentation. This is now our preferred
  citation. A CITATION.cff file is now included in the repo.

### Changed
- DESCRIPTION pointers will now be deduplicated and print with indexes in the 
keys list (e.g. DESCRIPTION_0, DESCRIPTION_1, etc.). No warning will be triggered.
- Unit tests have been moved inside the pdr/ folder and will now be packaged
and shipped with pdr
- Previously only pointers named exactly "^STRUCTURE" or "^PDS_OBJECT" skipped
  deduplication. Now all pointers with "STRUCTURE" in the name skip deduplication,
  and all pointers with "PDS_OBJECT" in the name get ignored.
- vendored `pdr.vax` module removed in favor of using SETI's `rms-vax` (successor 
  package to that vendored module)
- `pdr.pilutils` renamed to `pdr.pil_utils` for consistency
- `Data.get_scaled` and functions that use it (like `Data.dump_browse`) now also
  mask nonfinite values (inf, -inf, and nan)
- `pdr` no longer greedily heads files when looking for PVL labels
- Added a `check_special_block()` call to `Data.get_scaled`

### Fixed
- updated docs/LICENSE.md to match LICENSE.md
- `pillow`'s `DecompressionBombError` now fully suppressed when reading desktop
  format images in primary mode

### Removed
- `pdr` ignores all PDS3 pointers containing the string "PDS_OBJECT". `Data`
  previously returned a TBD message on attempts to access objects associated
  with these pointers. We have determined that these pointers were markers for
  internal software tools and do not refer to unique data objects.
- The text of our JOSS paper publication on pdr has been removed from
  `joss_paper/paper.md`. Please refer instead to the pdf under `docs/pdr_joss_paper.pdf`
- A warning is no longer raised for out-of-bounds values on converting to 8-bit
for browsification


## [1.2.3] - 2024-09-30

### Changed
- Consolidated optional 'browsify' and 'desktop_image' dependencies into simply 
  'pillow'.
- Any attempt to use functionality that requires an optional dependency now raises
  a `ModuleNotFoundError` naming the required module.
  - To support this, `astropy` objects are now always imported through 
    `loaders.astrowrap`.
- Updates to documentation to include instructions for pip users, etc. 

### Fixed
- `docs/index.md` updated to reflect the same content as README.md

### Removed
- Experimental `save_sparklines()` function in `pdr.browsify`, and along with 
  it, the optional matplotlib dependency.
- Unnecessary full `matplotlib` dependency for Notebook use.


## [1.2.2] - 2024-09-30
### Added

#### Features
- Support for 'desktop' image formats in primary mode: JPEG, TIFF, GIF 
  (still and animated), PNG, MPO/MPF, WebP (still and animated), JPEG2000/JP2, 
  and BMP. Behavior is as follows:
  - `pdr` will attempt to parse all EXIF, TIFF tag, and MPO metadata, including
  embedded XML packets. Parsed metadata is available in `Data.metadata` and 
  accessible with `Data.metaget()` and related methods.
  - Some basic image information is also available in `Data.metadata` (format, 
  color mode, dimensions, MIME type, etc.) 
  - Most files will have a single data object named 'IMAGE'.
  - Animated GIF and WebP images will have one data object per frame, named 
    'FRAME_0', 'FRAME_1', etc.
  - MPO/MPF files (this includes many files with .jpg and .jpeg extensions)
  will have one data object per image. The MPO primary image is named 'IMAGE'. 
  Subsequent images are assigned names based on their MPType and index within
  the file.
  - PDR automatically converts palette-mode images (like many GIFs) to 3D RGB
  arrays on load. In these cases, mappings between RGB values and original 
  palette indices are available with `data.metaget('palette')`.
  - GeoTiffs work like other TIFF files. `pdr` naively parses the GeoTiff 
  metadata, but does not construct a CRS or otherwise derive projection 
  information.
  - Note that some of PDR's convenience features like `Data.show()` do not 
    work well with images that rely on transparency.

#### Dataset Support
- additional Cassini ISS calibration images
- MRO HiRISE RDRs and additional DTM images (were notionally supported, now have official support)

#### Other
- The text of our JOSS paper publication on pdr is now included under 
  `joss_paper/paper.md`. It will be moved to `docs/paper.md` in next release.
- Clarifying comments were added to the supported_datasets documentation regarding
  spice files
- Community guidelines including a code of conduct and contribution guidelines
  have been added to the readme and docs folder

### Changed
- `Data.dump_browse()` and `.show()` no longer apply default contrast enhancement 
  if it would result in an image with only one value. Explicitly passing the
  `image_clip` argument will override this, if for some reason you want to.
- Levenshtein dependency is now optional. Users installing via pip will need to
  use the "fuzzy" option.
- `tiff` optional-dependency feature in has been changed to `desktop_image` for
  pip users to better fit with new features in this version 

### Fixed
- `Data.dump_browse()` now works correctly with FITS files opened in primary mode.

### Removed
- `CHANGELOG.md` was removed in preference of solely `docs/version_history.md`
- Binder demo of example notebook due to issues with Binder servers.

## [1.2.1] - 2024-09-18
### Added

#### Features
- Full compatibility with numpy 2.0 for pds4 products 
(pds3 products already compatible in last release)

### Changed
- `pds4_tools` is now vendored within `pdr` to apply changes for numpy 2.0 
compatibility and avoid hot patches

### Removed
- `pds4_tools` dependency
- `_patches` module

## [1.2.0] - 2024-09-18
### Added

#### Features
- Compatibility with numpy 2.0 for pds3 products and fits pds4 products
 (non-fits PDS4 product numpy 2.0 compatibility awaits changes in
 `pds4_tools` dependency)
- Support for VAX_REAL data types in qubes
- `pdr.Data.__contains__` method
[see issue #57](https://github.com/MillionConcepts/pdr/issues/57)
- Unit tests are now backed by `pytest` fixtures for improved flexibility and
compatibility
- ROW_PREFIX_BYTES are now accounted for when calculating offset positions

#### Dataset Support
- Galileo NIMS qubes
- MSL 
  - EMS EDRs and RDRs
  - additional navcam and hazcam RDRs
- Rosetta
  - CONSERT
  - ALICE supplementary tables
  - MIDAS RDRs
  - additional COSIMA tables
- LASP Mars datasets
- Venus Express (VEX)
- Phoenix
  - ASE EDRs, RDS
  - Telltale Experiment (TT) products
  - Atmospheric Opacity (AO) products
  - TEGA LED EDRs and SC RDRs
- MGN RSS solar wind experiment
- MGS RSS solar conjunction data
- MEX VMC EDRs and RDRs
- Mariner 10 MAG, PLS, and POS products
- WFF/ATM derived DEM images
- Misc additional products from:
  - Cassini RPWS, MIMI, and ISS
  - Galileo Probe, MAG, SSI
  - IHW
  - ground-based datasets at SBN and ATM
  - Stardust
  - LRO Mini-RF
  - NEAR NLR
  - ICE
  - Juno JADE
  - Pioneer Venus Orbiter OMAG
  - Vega
  - Voyager LECP
  - MEX PFS and MARSIS
  - MER navcam/hazcam/pancam RDRs

#### Other
- (GitHub-specific) CI for unit tests / coverage reports

### Changed
- PDR now associates FITS HDUs with PDS data objects by matching byte ranges 
  as described in PDS labels to HDU byte ranges as described in their FITS 
  headers, rather than by performing fuzzy string match between HDU names and 
  PDS object names
- PDS4 FITS files are now opened using `astropy.io.fits` on the backend 
  instead of `pds4_tools`, mirroring the PDS3 FITS behavior
- Non-filled-out FITS cards are represented as None, rather than special 
  astropy objects without stable byte representations
- Assorted backend refactoring, linting, and minor improvements
- Unit tests no longer unnecessarily write to the source tree
- All string objects loaded directly from products by `Data` ('DESCRIPTION', 
  'LABEL', etc.) canonicalize line endings to \n

### Fixed
- More compatibility fixes for Python 3.9, mostly related to type annotations
- Improved reliability of associating compressed files with filenames that
  imply uncompressed files (and vice versa)
- Addressed some cases in which PDR wasn't accurately determining lengths for
  HEADER objects
- HISTOGRAM_IMAGE objects will now be read as images instead of attempting
  to be read as tables. (IMAGE_HISTOGRAMS will still be read as tables)
- setup.py also correctly pins `numpy < 2.0.0`
- The hotpatch for `pds4-tools` Python 3.12 incompatibility no longer
  has persistent side effects; for instance, `conda` will no longer
  complain about checksum mismatches.
- Bug reading PDS4-labeled FITS files

### Removed
- `pdr.Data.__iter__` method is being deprecated
[see issue #57](https://github.com/MillionConcepts/pdr/issues/57)
- `pdr.Data.__getitem__` method is being deprecated 
[see issue #57](https://github.com/MillionConcepts/pdr/issues/57)

## [1.1.2] - 2024-06-18
### Changed
- Pinned numpy version to less than 2.0 until compatibility issues with new
release are resolved.


## [1.1.1] - 2025-06-14
### Fixed
- Bugfix for compatibility for Python 3.9 by adding two features of Python 3.10.
  - pdr.py: if inspect.get_annotations is not available, use a fallback
    implementation (incomplete, but works for the case we care about).
  - pdrtypes.py: if typing.TypeAlias is not available, define it by hand.


## [1.1.0] - 2024-05-21
### Added

#### Features
- Support for 4 bit VAX_REAL Tables
- Ability to modify Metadata objects and have changes propagate to pdr objects.
Suggested feature in issue [#55](https://github.com/MillionConcepts/pdr/issues/55)


    Example Usage:
    Display an BSQ RGB image as a vertical image with 
    each channel split into a column
    
    data.metadata['IMAGE']['LINES'] = (
    data.metadata['IMAGE']['BANDS'] * data.metadata['IMAGE']['LINES']
    )
    data.metadata['IMAGE']['BANDS'] = 1
    data.load_metadata_changes()
    data.load('IMAGE', reload=True)
    data.show('IMAGE')

    If the image was not loaded before the metadata change, the `reload=True` 
    argument is unnecessary. 

#### Dataset Support
- Cassini UVIS EUV, FUV
- Voyager IRIS full-res spectral observations
- GRSFE AVIRIS and TIMS tables
- all GRSFE TABLE_HEADER and SPECTRUM_HEADER pointers
  - Affected datasets: AVIRIS and TIMS tables, PARABOLA, and wind experiment

### Changed
- Updated several unit tests based on the Metadata changes

### Fixed
- Bug which prevented reading of single band images with an interleave key if 
the interleave was BIL and the image had prefix/suffix. Resolves issue 
[#55](https://github.com/MillionConcepts/pdr/issues/55)
- Bug in which some pds4 data objects were not being successfully cast from 
PDS4tools arrays to numpy arrays
- Bug in which padding bytes before top level containers in ASCII tables not 
described by a column in the label were not being respected. See below for 
description of this type of label writing practice.
  ```
  michael: yeah. the problem is that this isn't actually wrong, it's just depraved.
  it violates only the spirit of the law
  ```

## [1.0.7] - 2024-04-23
### Added

#### Features
- `pdr.fastread()`, a convenience function for opening a product without
  checking for a detached label. This function only works if you point it at 
  the file that contains the product's label (attached or detached). Improves 
  speed on slow filesystems or for large numbers of products, particularly 
  when you are only interested in their metadata or the data objects you want
  to load from them are small.

#### Dataset Support
- MEX SPICAM and MRS datasets
- Comet D/Shoemaker-Levy 9/Jupiter Impact Observing Campaign datasets
- see [supported_datasets.md](docs/supported_datasets.md) for details

#### Other
- Lots of docstrings, type hinting, and other in-code documentation
- Additional shared types to support static analysis and code readability
- `pdr-tests`-compatible annotations for special cases

### Changed
- Assorted code refactoring, linting, and minor backend improvements
- Substantial performance increases for wide tables with many repeated items
- Modified some special cases for pandas 2.2.x compatibility

### Fixed
- A bug in PDS4 label handling that sometimes dropped repeated child elements
- An accidentally-skipped out-of-date unit test for DSV tables 
- Slow imports are again delayed until needed

### Removed
- Unused numpy-based ASCII table parser  

## [1.0.6] - 2024-03-28
### Added
#### Features
- `Data` now directly affords a `find_special_constants()` method   

#### Dataset Support
- most IHW datasets
- additional Voyager 1 and 2 datasets
- GRSFE and WFF/ATM datasets
- LOIRP dataset
- additional MSL, Apollo, and Mariner datasets
- additional Earth-based lunar data
- Viking Lander datasets
- Mars Odyssey DAN and SAM data 
- MEX ASPERA, HRSC, SRC, and PFS data
- most Phoenix TEGA, ELEC, and WCL products
- see [supported_datasets.md](docs/supported_datasets.md) for details

### Changed
- Assorted type-hinting and other in-code documentation improved.
- Behavior for character stripping in string columns of ASCII tables was 
  inconsistent. To increase usability, string columns of ASCII tables now 
  discard preceding and trailing spaces, commas, newlines, and double-quotes 
  (regardless of strict label specification).
- Generally improved performance on table reading

### Fixed
- Incorrect column bounds due to unusual prefix/suffix/infix specifications 
  in some ASCII tables 
- Incorrect column bounds due to container padding in some tables
- FITS HDUs with non-printable characters in header cards will now load,
  discarding any such cards from the header (unless the cards are required, 
  e.g. NAXIS1) Resolves issue [#52](https://github.com/MillionConcepts/pdr/issues/52)

## [1.0.5] - 2023-12-07
### Added
#### Features
- doc strings for API on readthedocs
- Error tracking features that were accidentally deleted from the last version were re-added
#### Dataset Support
- most Voyager 1 and 2 datasets
- additional MGS datasets (MAG/ER, RSS EDS, MOC)
- Mariner 9 datasets
- Pioneer 10 and 11 GTT RDRs
- Sakigake, Suisei, and SOHO datasets
- ICE and IUE datasets
- see [supported_datasets.md](https://github.com/MillionConcepts/pdr/blob/main/supported_datasets.md) for details.

### Fixed
- Tables with containers with REPETITIONS in them were reading the same data each repetition, this has been fixed
- Exponential notation in pvl quantity objects are now properly handled

### Removed
- MRO MCS DDR data is not supported due to formatting issues

## [1.0.4] - 2023-10-23
### Added
#### Features
- support for GIF files referenced as PDS3 objects
- improved verbosity of some file-not-found error messages

#### Dataset Support
- MER 1 and 2
- Ulysses
- see [supported_datasets.md](https://github.com/MillionConcepts/pdr/blob/main/supported_datasets.md) for details.

### Changed
- updated install specifications
- added hotpatch to address `pds4-tools` Python 3.12 incompatibility, 
to be removed following `pds4-tools` 1.4 release

### Fixed
- correctly interpret PVL non-decimal integer representations as 
  `int(non_decimal_integer, base=int(radix))`. e.g., `pdr` will now interpret 
   the PVL statement:

   ```
    "SAMPLE_BIT_MASK          = 2#1111111111111111#"
   ```
  
   as a metadata item with key "SAMPLE_BIT_MASK" and value 65535.

   Please note that the bit masks are not applied programmatically because we don't believe 
   their meanings are consistent across the corpus of planetary data. However, users are 
   encouraged to explore their use within their own work and enjoy the glories of the Python `&` operator.

   An example for how to apply a bit mask using the `&` bitwise operator:

    data = pdr.read('/path/to/file.img')
    masked = data.IMAGE & data.metaget('SAMPLE_BIT_MASK')
   
   Alternatively, if you're using this value for something for which you'd prefer to have the original PVL 
   value, use the `bin`, `oct`, or `hex` packages for base 2, 8, or 16 respectively to convert the value
   back from an integer.

  ([Resolves issue #51](https://github.com/MillionConcepts/pdr/issues/51))
- correctly interpret PVL Sequences and Sets of Unquoted Strings as 
  `tuple[str]` or `set[str]` respectively
- fix some cases in which PVL End Statements were incorrectly interpreted 
  as parameters with empty-string values

## [1.0.3] - 2023-10-03
### Added
#### Features
- FITS files can now be opened 'directly' (without a PDS label). 
See [README.md](https://github.com/MillionConcepts/pdr/blob/main/README.md) for more detailed usage.
- 1d, non-structured ARRAY objects are now compatible with `dump_browse`
- support for ARRAY objects with nested ARRAY or COLLECTION objects
- [`pytest`-compatible unit test suite](https://github.com/MillionConcepts/pdr/blob/main/pdr/tests/) 
intended to complement our [comprehensive regression test framework](https://github.com/MillionConcepts/pdr-tests)

#### Dataset Support
- most New Horizons datasets
- Venera 15 and 16 derived data
- Giotto PIA and VEGA 1/2 Puma_mode data
- Venus Climate Orbiter data
- Saturn Ring Plane Crossings (RPX) 1995-1996 data
- most Phoenix datasets
- Deep Impact and EPOXI data
- Mars Pathfinder data
- several MRO datasets including HiRISE EDRs, MCS, MARCI, and CTX
- see [supported_datasets.md](https://github.com/MillionConcepts/pdr/blob/main/supported_datasets.md) for details.

### Changed
- Debug-mode error tracking is substantially more detailed
- Debug-mode error logs are now written as JSON
- Assorted backend refactoring, cleanup, error checks, and in-code documentation

### Fixed
- Fixed incorrect PDS3 object -> FITS HDU mapping for several data types
- scaling/offset defined in FITS tables (BSCALE/BZERO) is now applied correctly to output `DataFrames`  
- 8-byte integers found in some nonstandard binary files are now handled correctly
- more consistent handling of long / malformatted PVL comments
- improved handling of 'stub' primary FITS HDUs


## [1.0.2] - 2023-08-01
### Added
#### Features
- Support for FITS tables
- Documentation on behavior of FITS files (in README)
- Support for VAX floating-point numbers
#### Dataset Support
- Rosetta ALICE EDR, RDR, and REFDR data
- several Galileo datasets
- sampleninterleaved (BIP) images, including:
  - DAWN VIR EDR and RDR cube products
  - Rosetta VIRTIS EDRs
- Deep Space 1, NEAR, Stardust, and Stardust-NExT datasets
- various image products stored as VAX floats, including Pioneer Venus radar and IMIDR images
- IBM_REAL and EBCIDC data types, including Pioneer Venus SEDR
- LRO CRaTER EDR secondary science and housekeeping tables
- several Mars Odyssey datasets
- several Vega datasets

### Changed
- TABLE and SERIES objects now apply label provided offset and scaling factors. 
  This has not yet been implemented for ARRAY objects or BIT COLUMNS.
- License file updated to incorporate license from the vendored vax.py module.

### Fixed
- Tables with nested containers now read correctly; closes [issue 50](https://github.com/MillionConcepts/pdr/issues/50)
- ^STRUCTURE pointers inside a COLUMN/FIELD now correctly load the relevant format file 

### Removed
- Spaces in BIT_COLUMN DATA_TYPE values no longer raise `UserWarning`s

## [1.0.1] - 2023-06-20
### Fixed
- re-enabled the ability to import `pdr.Data` by adding it back to `__init__.py`

## [1.0.0] - 2023-06-03
This release represents a major refactoring effort to reduce technical debt and decrease workflow complexity. 
**The user-facing `pdr.read()` interface has not changed.**
###  Added
#### FEATURES
- `pdr.Data`  initialized with `debug=True`
  - Errors can be inspected at runtime by accessing `Data.loaders["OBJECT_NAME"].errors`.
  - Tracking logs are also saved to the `pdr/.tracker_logs` folder.  
  directory of the installation folder. They show which functions `Data` objects
  used during loading processes -- and if those functions were successful.
- handling for a wider array of ISIS-style "qube" data and metadata, 
  including side/back/bottom/topplanes (as long as they are along only one
  image axis)
#### Dataset Support
- most THEMIS qube products
- TODO for cassini XDR image scaling functionality
- additional LRO datasets: CRaTER, LAMP, LEND, LOLA, Mini-RF, and Radio Science
- several Venusian datasets including: Magellan GVDR, Pioneer Venus, 
  "Pre-Magellan" products at the GEO node, and Earth-based radar observations.
- several Lunar datasets including: GRAIL, Lunar Prospector, MSX, 
  Kaguya/Selene, and Earth-based radar and spectroscopy data.- (most) THEMIS qube products
- TODO for cassini XDR image scaling functionality
- additional LRO datasets: CRaTER, LAMP, LEND, LOLA, Mini-RF, and Radio Science
- several Venusian datasets including: Magellan GVDR, Pioneer Venus, 
  "Pre-Magellan" products at the GEO node, and Earth-based radar observations.
- several Lunar datasets including: GRAIL, Lunar Prospector, MSX, 
  Kaguya/Selene, and Earth-based radar and spectroscopy data.

### Changed
- reworked fundamental data loading workflow. `Data` class no longer contains 
  all the loader functions, they've been refactored in the `loaders` module.
- `formats.core.py` now only contains special case checking functions and is renamed to `formats.checkers.py`.
  Other functions that were previously in it (like `pointer_to_loader` and `generic_image_properties`) have 
  moved to the `loaders` module
- changes to various special cases based on the data loading workflow refactor
- reworked image-loading flow for better handling of various band storage
  types and pre/suffixes
- BIL images now retain original byteorder
- reworked cassini xdr special case for compatibility

### Fixed
- discovered some rosetta VIRTIS and cassini UVIS product types were not 
  actually reading correctly, marked them out of support

### Removed
- m3 special case module (deprecated by new image-loading flow)
- messenger special case module (deprecated by new data loading workflow)
- rasterio loading options for image data
- `check_special_case` has been removed and the special cases have been moved to functions
  that more specifically targeted to the issues of the particular dataset rather
  than overriding the entire workflow.

## [0.7.5] - 2023-03-16
### Added
 - support for a variety of Magellan data (see [supported_datasets.md](https://github.com/MillionConcepts/pdr/blob/main/supported_datasets.md) 
   for specifics)

### Changed
 - sample types are now more permissive and allow spaces
 - line endings are less strict and allow between 0-2 carriage returns 

### Fixed
 - HiRISE EDRs are now only listed as notionally supported (rather than known 
   unsupported and notionally supported)

### Removed
 - special case for mgs-rss data with IEEE REAL sample types (now supported in core 
   functionality)

## [0.7.4] - 2023-03-13
### Added
#### Features
 - This change log file
 - Support for bit columns with ITEMS
 - Browse images can now be output in grayscale
 - handling for COMPRESSED_FILE objects 
#### Dataset Support
 - a variety of LRO Diviner, Cassini, and Huygens data products    
   (see [supported_datasets.md](https://github.com/MillionConcepts/pdr/blob/main/supported_datasets.md) 
   for specifics)

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
#### Features
 - Array pointers are now supported
 - FITS headers are now supported. (If a pointer with HEADER in it points to a FITS
   file it will return that header. If there is a pointer without HEADER in it that 
   points to the FITS file then after loading that key, an additional key will appear 
   in the format: `{key}_HEADER` that will contain the FITS header).
 - JPEG2000 (`.jp2`) files are now supported
#### Dataset Support
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
#### Features
 - better search functionality for format files (description of behavior/usage can be found 
   [here](https://github.com/MillionConcepts/pdr/issues/36#issuecomment-1276764335))
 - A pretty printer for label metadata is now available. (Use print(data.metadata) to see the
   nicely formatted label information)
 - Image data with different scales and offsets can now be used with the browse products 
   created by `get_scaled`
#### Dataset Support
 - several Juno datasets (see supported_datasets.md for specifics).

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
