# Datasets Supported by `pdr`

"Support" from `pdr` falls into two categories: official and notional.

**_Officially supported datasets_** have been extensively tested and all of
their products are supported. If you encounter a file of this type that does not
open with pdr, please open an issue at: 
https://github.com/MillionConcepts/pdr/issues

**_Notionally supported datasets_** have been manually tested with a small
number of files. Some of these sets do not conform to PDS standards in ways
that prevent us from ever testing them to our standard for official support 
(for instance, they might lack label files). Others in this category will be 
moved to official support after more rigorous testing.

Many datasets that do not fall into either of these categories may work
just fine. They are not listed simply because we have not had a chance to 
test them yet.

Some datasets are also **_Known unsupported_**. Some files or objects may
open, while others may not; those that do may open incorrectly. Support is
planned for some of these datasets. Others—due to unusual data formats,
availability, or quality issues—may never be supported.

**All PDS4 products, unless explictly listed here as known unsupported or specified
in [`pds4_tools`](https://github.com/Small-Bodies-Node/pds4_tools/) documentation
as out of support, are considered at least notionally supported**. We 
give specific comments and usage suggestions about some PDS4 product types below. 
PDS4 products are much more rigorously standardized and validated than PDS3 
products, allowing the `pds4_tools` developers to make very broad support 
claims that we consider trustworthy. All currently-known exceptions are due 
to data QA problems rather than deficiencies in `pds4_tools`. 

As a general note, our confidence is generally lower about products that
contain raw telemetry (or other forms of unprocessed data) or that use 
bespoke compression schemes. Fully validating our outputs for these products 
would require recreating portions of ground processing pipelines, which is 
outside the scope of this project. "Support" for these types means that they 
load correctly into expected data structures and that interpretable portions 
of their metadata appear to match other sources.


## Officially Supported Datasets:

- LROC
  - WAC EDR and CDR
  - NAC EDR, CDR, and raw image data (NACR and NACL in image name)
  - NAC DTM
  - WAC Derived products: EMP, HAPKE, HAPKE PARAMMAP, ORBITS, POLE ILL, TIO2
- MRO
  - CRISM EDR, CDR, DDR, LDR, TER, TRDR, MRDR, and MTRDR
  - CRISM speclib and typespec tables
  - SHARAD EDR and RDR
  - SHARAD rgram and geom files
  - RSS ODF, RSR, RSDMAP, SHADR, and SHBDR
- MSL
  - Hazcam EDR and RDR (including ops parameter maps)
  - Navcam EDR and RDR (including ops parameter maps)
  - Mastcam, MAHLI, and MARDI RDRs
  - CCAM LIBS EDR, L1B, and L2; CCAM RMI EDR and RDR
  - APXS EDR and RDR (*note: the EDR checksum suffix is not supported*)
  - Chemin L1B and L2 RDRs, and EDRs
- Chandrayaan-1
  - M3 L0, L1B, and L2 images and ancillary files 
  (*note: L0 line prefix tables are not currently supported*)
- Galileo 
  - magnetometer tables (except summary tables)
- Juno
  - FGM tables
  - Gravity Science tables (EDR, RSR, and TNF)
- Apollo
  - all PDS3 datasets that have not been deprecated by PDS4 versions. 
    specifically:
    - Apollo 12 and 15 Solar Wind Spectrometer tables
    - Apollo 15 and 16 X-ray Fluorescence Spectrometer tables
    - Apollo 14 and 15 Cold Cathode Ion Gage digitized plots and index tables
    - Apollo 15 and 16 Lunar Self-Recording Penetrometer transcribed tables
    - BUG soil reflectance tables
- Mars Express
  - MARSIS EDRs and RDRs
- Mars Odyssey
  - THEMIS BTR, ABR, PBT, and ALB
- MGS
  - TES-TSDR ATM, BOL, GEO, OBS, POS, TLM, IFG and RAD (fixed-length tables only)
  - TES Thermal Inertia and Albedo maps
  - MOLA PRDR, IEGDR (v1 and v2), MEGDR, and SHADR
  - RSS ECH, ECS, ECT, FBR, MCH, MCT, and RSR 
    - *note: ECH and MCH should have 'CSV' in their filenames*
- MESSENGER
  - GRNS EDR, RDR, CDR, DDR, and DAP
  - MASCS EDR, CDR, DDR, and DAP
  - MLA EDR, RDR, RADR, CDR, and GDR
  - XRS EDR, RDR, and CDR
    - *note: RDR maps are defined differently in their PDS3 and PDS4 labels. We recommend opening them from their PDS4 labels.*
  - RSS EDR and RDR
    - *note: Opening RDR SHADR files from their PDS4 labels is recommended.*
  - Space Weathering maps
  - MEAP electron events tables, thermal neutron map, and image cubes

## Notionally Supported Datasets:
- MRO
  - HiRISE RDRs 
- LROC
  - Anaglyphs
  - NAC DTM without labels (under EXTRAS folder at LROC mission node)
  - WAC derived tif files without labels (under EXTRAS folder at LROC
  mission node)
- Juno
  - JunoCam EDRs and RDRs
  - JIRAM EDRs and RDRs *note: RDRs may not read correctly from their PDS4
  labels. We recommend opening them from their PDS3 labels.*
  - JEDI EDRs and RDRs
  - MWR *note: performance is better if read from the PDS3 labels. this
  requires .FMT (format) files, available in the root directories of the MWR
  volumes.*
  - JUGN EDRs *note: most will open from PDS4 .xml labels only; RSRs open more
  efficiently from PDS3 labels*
  - Juno Waves reduced tables
  - JADE EDRs and RDRs
- Apollo
  - PDS3 versions of Apollo 15 and 17 Heat Flow Experiment tables -- 
    however, we recommend using the PDS4 collection a15_17_hfe_concatenated,
    which contains corrections and additional data, instead
- MGS
  - RSS Science Data Products (except PostScript files)
    - *note: There is a known issue where header tables and other ancillary tables open with their corresponding data tables appended as additional rows. Additionally, some '.IMG' products do not open because of a typo in their labels. (A fix for this is planned)*

## Known Unsupported Datasets
- MRO
  - HiRISE EDRs (IMAGEs from these may open, but we suspect not correctly; other packed binary objects may not)
  - RSS .tnf (support not planned)
- MSL
  - Malin Space Science Systems (MSSS) Camera EDRs: "Raw" (EDR) data from the
    Mars Science Laboratory's MSSS-produced cameras (Mastcam, MAHLI, and
    MARDI), are archived in a bespoke compressed format. These images carry
    the extension '.DAT'. Software for converting these files to PDS3-style
    uncompressed raster .IMG files exists in the archive. We plan to either include / compile this code with the installation of this package or (much better) to port `dat2img` to pure
    Python. Help is welcomed with either of these efforts! The MSL
    "calibrated" (RDR) files for these cameras are not compressed in this way.
- Juno
  - UVS (support planned)
  - Waves EDR (support not planned)
- Galileo
  - magnetometer summary tables (other tables supported)
- Mars Odyssey
  - THEMIS EDR, RDR, and GEO (support planned)
- MGS
  - TES-TSDR PCT (support not planned)
  - TES-TSDR variable-length '.VAR' tables (support not planned)
  - MOLA AEDR and PEDR (support planned)
  - RSS '.IMG' products with filenames beginning with 'j' (support planned)
    - *These files have a label formatting error.*
  - RSS ODR, ODF, and TDF(support planned)
    - *ODF and TDF products open with errors, ODR products do not open at all*
  - RSS Raw Data products with a "stream" or undefined RECORD_TYPE (support not planned)
  - RSS PostScript files from both Raw Data and Science Data Products (support not planned)
- MESSENGER
  - Ground calibration data (support not planned)
  - MEAP enhanced gamma ray spectrometry data

