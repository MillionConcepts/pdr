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
- Apollo
  - all PDS3 datasets that have not been deprecated by PDS4 versions. 
    specifically:
    - Apollo 12 and 15 Solar Wind Spectrometer tables
    - Apollo 15 and 16 X-ray Fluorescence Spectrometer tables
    - Apollo 14 and 15 Cold Cathode Ion Gage digitized plots and index tables
    - Apollo 15 and 16 Lunar Self-Recording Penetrometer transcribed tables
    - BUG soil reflectance tables
- Cassini
  - CAPS EDRs, RDRs, and DDRs
  - CDA
    - DA area, counter, events, settings, signal, spectra peaks, and status history tables
      - *Note: Many of the spectra products are placeholder tables composed of missing data constants. These placeholders are not supported.* 
    - HRD raw and processed data
  - CIRS navigation and housekeeping data
  - CIRS reformatted products at the RMS node (calibrated spectra)
  - INMS level 1A products and housekeeping data
  - ISS EDRs, MIDRs, and calibration data
  - MAG REDRs, RDRs, and most housekeeping data
  - MIMI EDRs and RDRs
  - RADAR ABDR, ASUM, BIDR, LBDR, SBDR, and STDR
  - RPWS REFDRs, RDRs, and DDRs
    - *Note: The RDR LRFULL tables include a MINI_PACKET_HEADER column which uses an illegal data type and could not be parsed.*
  - RSS gravity, occultation, solar, and bistatic experiments
  - RSS ancillary products: ODF, TDF, TLM, 158, and 515
  - Saturn rings occultation profiles derived from RSS, UVIS, and VIMS data
  - Saturn small moon and Gaskell shape models
  - UVIS HDAC products
  - VIMS EDR cubes (PDS4 labels only)
  - All Huygens Probe data except DISR IR tables
- Chandrayaan-1
  - M3 L0, L1B, and L2 images and ancillary files 
  (*note: L0 line prefix tables are not currently supported*)
- Clementine
  - Map-projected Basemap, HiRes, NIR, and UVVIS mosaics
    - These have been migrated to PDS4, pending archive approval.
  - Gravity and topography derived products
  - LWIR RDRs
  - RSS bistatic radar RDRs
  - LIDAR data *note: This is a saved PDS data set, not a regular PDS archive, but it can be opened with `pdr`*
- Dawn
  - Framing Camera: EDRs, RDRs, mosaics, shape models, and most calibration images
  - VIR: mosaics, EDR and RDR cube products
  - RSS: gravity models
- Deep Space 1
  - IDS RDRs
  - MICAS DEM, images, and matrices
- Galileo 
  - EPD: calibrated Jupiter data (PDS4) and pre-Jupiter products (PDS3)
  - GDDS tables 
  - HIC tables *note: Only the PDS4 versions have been tested here*
  - MAG tables (except summary tables)
  - NIMS: Pre-Jupiter EDRs, SL-9 fragment impact tables, and Ida/Gaspra specific data products at SBN
  - PLS: calibrated/derived Jupiter data (PDS4) and pre-Jupiter products (PDS3)
  - PPR: EDRs and RDRs
  - PWS: REDRs (ASCII versions), DDRs, and SUMM products
  - RSS: Jupiter and Io ionosphere electron density profiles
  - SSD: derived electron flux data
  - SSI: 
    - Calibration images
    - REDRs (images only)
    - Ida/Gaspra specific data products at SBN
  - UV: UVS and EUV *note: They open correctly from their PDS4 labels, but the PDS3 labels are currently unsupported.*
  - Probe datasets: ASI, EPI, HAD, LRD, NEP, NFR, and most DWE and NMS products
  - Trajectory data
- Giotto
  - DID RDRs
  - GRE RDRs
  - HMC RDRs
  - IMS HIS and HERS RDRs
  - JPA DDRs
  - MAG RDRs
  - NMS ion and neutral gas RDRs
  - OPE RDRs
- GRAIL
  - LGRS RDR: SHADR, SHBDR, and RSDMAP
  - RSS: BOF, ODF, OLF, and RSR
- Juno
  - FGM tables
  - Gravity Science tables (EDR, RSR, and TNF)
  - JADE EDRs and RDRs
  - JEDI EDRs and RDRs
  - JIRAM EDRs and RDRs *note: RDRs may not read correctly from their PDS4
  labels. We recommend opening them from their PDS3 labels.*
  - JunoCam EDRs, RDRs, and maps
  - MWR EDRs and RDRs *note: performance is better if read from the PDS3 labels. this
  requires .FMT (format) files, available in the root directories of the MWR
  volumes.*
  - Waves RDR 'Burst' tables
- Kaguya/Selene
  - Spectral Profiler data
  - other datasets have been migrated to PDS4 and are notionally supported
- Lunar Prospector
  - all PDS3 datasets that have not been deprecated by PDS4 versions. 
    specifically:
    - LOSAPDR
    - ER: RDR, SUMM, and level 2 products
    - MAG: SUMM, and level 2, 3, and 4 products
- LRO
  - CRaTER EDR secondary science and housekeeping tables, CDR, and DDR
  - DIVINER
    - EDR and RDR tables
    - L2 and L3 GDR images/backplanes
    - L4 tables
  - LAMP 
    - EDR and RDR (except acquisition list tables and spectral image 'door open' headers)
    - GDR
  - LEND EDR and RDR
  - LOLA RDR (*note: other LOLA datasets have been migrated to PDS4 and are notionally supported*)
  - LROC
    - WAC EDR and CDR
    - NAC EDR, CDR, and raw image data (NACR and NACL in image name)
    - NAC DTM
    - WAC Derived products: EMP, HAPKE, HAPKE PARAMMAP, ORBITS, POLE ILL, TIO2
  - Mini-RF
    - Bistatic Radar EDR, RDR, and DDR
    - Global mosaics
    - SAR raw, level 1 and level 2 data
  - Radio Science RANGE, SFF, TRK, and WEA
- Lunar Radar (Earth-based)
  - 70 cm radar maps
  - 12.6 cm (S-band) backscatter maps
- Lunar Spectroscopy (Earth-based)
  - RELAB spectra
- Magellan
  - FMAPs
  - Stereo-Derived Topography
  - C-BIDR images *note: `pdr` reads these correctly as the labels are written, but there are unaccounted for offsets in the images.*
  - F-MIDR and C-MIDR
  - GxDR: GTDR, GEDR, GSDR, and GREDR
  - GVDR
  - BSR raw data and calibrated spectra
  - LOSAPDR
  - Spherical Harmonic, Topography, and Gravity models and maps
  - Occultation raw data and derived profiles
  - Radio Tracking Data (except ODF3B tables)
- Mars Express
  - MARSIS EDRs and RDRs
- Mars Odyssey
  - THEMIS 
    - spectral qubes: VIS and IR v2 geoprojected images, VIS EDR and RDR,
      IR EDR
      - *note: ISIS history and header objects are not supported. Also, some
        products have sideplanes giving destripe metadata; these sideplanes 
        are discarded rather than returned to the user.* 
    - derived products: BTR, ABR, PBT, and ALB
  - MARIE/MAR REDRs and RDRs
  - GRS suite
    - GRS EDRs, corrected spectra, and summed spectra
    - NS EDRs, averaged spectra, and derived data
    - HEND EDRs, averaged spectra, and derived data
    - Element concentration maps
    - special data products
    - improved derived neutron data (PDS4)
  - RSS ODF, RSR, and TDF products
- MESSENGER
  - GRNS
    - NS EDR, CDR, DDR
    - GRS EDR, RDR, CDR, DAP
  - MASCS
    - UVVS EDR, CDR, and DDR
    - VIRS EDR, CDR, DDR, and DAP
  - MLA EDR, RDR, RADR, CDR, and GDR
  - XRS EDR, RDR, and CDR
    - *note: RDR maps are defined differently in their PDS3 and PDS4 labels. We recommend opening them from their PDS4 labels.*
  - RSS EDR and RDR
    - *note: some EDR products (DDOR and TNF) have UNDEFINED record types in their PDS3 labels. We recommend opening them from their PDS4 labels.*
  - Space Weathering maps
  - MEAP electron events tables, thermal neutron map, enhanced gamma ray spectrometry data, and image cubes
  - Ground calibration data (aside from NS and MASCS)
- MGS
  - TES-TSDR ATM, BOL, GEO, OBS, POS, TLM, IFG and RAD (fixed-length tables only)
  - TES Thermal Inertia and Albedo maps
  - MOLA PRDR, IEGDR (v1 and v2), MEGDR, and SHADR
  - RSS most Raw Data and Science Data Products (see Known Unsupported Datasets below for excluded products)
- MRO
  - CRISM EDR, CDR, DDR, LDR, TER, TRDR, MRDR, and MTRDR
  - CRISM speclib and typespec tables
  - SHARAD EDR and RDR (*note: EDR science telemetry tables will only open the "science data" column(s) and does not output the columns described in the science_ancillary.fmt)
  - SHARAD rgram and geom files
  - RSS ODF, RSR, RSDMAP, SHADR, and SHBDR
- MSL
  - Hazcam EDR and RDR (including ops parameter maps)
  - Navcam EDR and RDR (including ops parameter maps)
  - Mastcam, MAHLI, and MARDI RDRs
  - CCAM LIBS EDR, L1B, and L2; CCAM RMI EDR and RDR
  - APXS EDR and RDR (*note: the EDR checksum suffix is not supported*)
  - Chemin L1B and L2 RDRs, and EDRs
- MSX
  - Infrared Minor Planet Survey
  - Small Bodies Images
  - Zodiacal Dust Data
- NEAR
  - GRS EDRs, L2 and L3 products
  - MAG EDRs and RDRs
  - MSI raw data, IOFs, RADs, DIMs, and shape models
  - NIS EDRs and L2 products
  - NLR EDRs, CDRs, and shape models
  - RSS spherical harmonic models, gravity acceleration maps, Eros landmarks table, and ODFs
  - XRS EDRs, L2 and L3 products
- Pioneer Venus Orbiter
  - OEFD HIRES data and 24 second averages
  - OETP HIRES and LORES electron data, bow shock and ionopause crossings, and solar EUV data
  - OIMS HIRES data and 12 second averages
  - OMAG
    - P-sensor HIRES data and 24 second averages
    - Spacecraft coordinates HIRES data and 24 second averages (*note: only the binary versions have been extensively tested*)
  - ONMS HIRES data and 12 second averages
  - ORPA processed data
  - OUVS IMIDR images
  - POS VSO coordinates
  - POS SEDR
- Pre-Magellan collection at the GEO node
  - AIRSAR images
  - Earth-based Mars, Mercury, Lunar, and Venus observations
  - Pioneer-Venus orbiter radar and gravity tables, and most radar images
  - Viking orbiter gravity data
- Rosetta
  - Orbiter:
    - ALICE EDRs, RDRs, and REFDRs
    - COSIMA images and feature tables
    - GIADA EDRs, RDRs, and DDRs
    - MIDAS RDRs and DDRs (excluding those with a .dat file extension)
    - MIRO EDRs and RDRs
    - NAVCAM EDRs and RDRs
    - OSIRIS EDRs, RDRs, DDRs, and shape models
      - *note: Images are archived in both .img and .fit file formats. The .img products have attached labels, while the .fit products have detached labels. When downloading the data, make sure to store these in separate directories or pdr will try to open the .img products using the detached labels.*
    - ROSINA EDRs, RDRs, and DDRs
    - Rosetta Orbiter Plasma Consortium Instruments:
      - RPCICA EDRs, RDRs, REFDRs, and DDRs
      - RPCIES EDRs, RDRs, and DDRs
      - RPCLAP EDRs, RDRs, and DDRs
      - RPCMAG EDRs, RDRs, and REFDRs
      - RPCMIP RDRs
    - RSI EDRs and RDRs
    - SREM EDRs and DDRs
    - VIRTIS DDRs
  - Lander:
    - APXS EDRs
    - COSAC EDRs and RDRs
    - MODULUS/Ptolemy EDRs, RDRs, and DDRs
    - MUPUS EDRs and RDRs
    - ROLIS EDRs and RDRs
    - ROMAP EDRs, RDRs, and DDRs
    - SD2 RDRs
    - SESAME EDRs and RDRs
- Stardust
  - CIDA EDF and housekeeping data
  - DFMI products
  - DSE products
  - NAVCAM EDRs, RDRs, derived shape models, and pre-flight calibration images
  - SRC temperature and geometry data
- Stardust-NExT
  - CIDA
  - DFMI
  - NAVCAM EDRs and RDRs
  - Derived shape models
- Vega 1 and 2
  - TVS raw, processed, and transform images
  - IKS raw and processed data
  - DUCMA data
  - SP-1 and SP-2 data
  - PM1 data
  - TN-M data
  - MISCHA data
  - Stooke Shape Models
  - Balloon and lander EDRs and RDRs
- Venus Radar Data (Earth-based)
  - Uncalibrated, Delay-Doppler Images
  - Calibrated, Multi-Look Maps

## Notionally Supported Datasets:
- Apollo
  - PDS3 versions of Apollo 15 and 17 Heat Flow Experiment tables -- 
    however, we recommend using the PDS4 collection a15_17_hfe_concatenated,
    which contains corrections and additional data, instead
- Cassini
  - CIRS spectral cubes
- Juno
  - JUGN EDRs *note: most will open from PDS4 .xml labels only; RSRs open more
  efficiently from PDS3 labels*
- LROC
  - Anaglyphs
  - NAC DTM without labels (under EXTRAS folder at LROC mission node)
  - WAC derived tif files without labels (under EXTRAS folder at LROC
  mission node)
- MRO
  - HiRISE RDRs
- MSL
  - CheMin Film EDRs (have efm in filename)
- MSX
  - QUBE images
- Pioneer Venus Orbiter
  - OMAG spacecraft coordinates: HIRES data and 24 second averages (ASCII versions)
- Rosetta
  - Orbiter:
    - VIRTIS EDRs
  - Lander:
    - ROMAP calibrated housekeeping data *note: There are multiple format files for these products that share a name but handle the data differently. If there are unexpected offsets in a table, confirm you are using the correct 'romap_calhk.fmt' file.*

## Known Unsupported Datasets
- Cassini
  - CIRS variable-length '.VAR' tables (support not planned)
  - ISS telemetry and prefix tables (support planned)
  - MAG error count housekeeping data
  - RPWS telemetry data
  - RSS ancillary products: TDF, TLM, PD1, PD2, TNF, EOP, ION, and TRO (support not planned)
  - VIMS EDR cubes (PDS3 labels; support not planned--open with PDS4 labels)
  - UVIS EUV/FUV products (support planned)
  - Huygens Probe DISR IR tables (support planned; low priority )
- Clementine
  - Imaging EDRs (basemap, HiRes, NIR, and UVVIS) (support not planned)
  - LWIR EDRs (support not planned)
  - RSS EDRs (support not planned)
- Dawn
  - Framing camera: a handful of calibration images
- Galileo
  - MAG summary tables (other tables supported)
  - NIMS Jupiter EDRs and cubes (support planned)
  - SSI REDR telemetry and line-prefix tables (support planned)
  - PLS EDRs (support not planned)
  - PWS EDRs, binary REDRs, and REFDRs (support planned)
- Giotto
  - GRE EDRs (support not planned)
  - PIA (support planned)
- GRAIL
  - LGRS: EDR and CDR (support not planned)
  - RSS: BTM, TDM, TNF, XRF, and ancillary products (support not planned)
- Juno
  - JADE Ion sensor housekeeping data prior to arrival at Jupiter (support not planned)
  - UVS (support planned)
  - Waves EDR (support not planned) and RDR 'Survey' tables (support planned)
    - *Currently, these are available at the PPI node in .csv format and can be opened with Excel.*
- LRO
    - CRaTER EDR primary science data (support not planned)
    - LAMP EDR/RDR acquisition list tables and spectral image 'door open' headers (support planned)
- Magellan
  - C-BIDR ancillary tables (support not planned)
  - F-BIDR (support not planned)
  - ALT-EDR (support not planned)
  - ARCDR (support planned)
  - SCVDR (support not planned)
  - BSR calibrated time samples (support planned)
  - Radio Tracking ODF3B tables (support planned)
  - RSS solar wind experiment ('safed' dataset)
  - SAR EDR ('safed' dataset)
- Mars Odyssey
  - THEMIS
    - IR RDRs (support planned)
    - v1 VIS/IR geoprojected products (support not planned. v2 are supported. 
      v1 is, per data providers, unsuitable for science due to cosmetic 
      processing)
  - RSS products not listed above as supported (support not planned)
- MESSENGER
  - Ground calibration data for MASCS and NS (support not planned)
- MGS
  - TES-TSDR PCT (support not planned)
  - TES-TSDR variable-length '.VAR' tables (support not planned)
  - MOLA AEDR and PEDR (support planned)
  - RSS Raw Data products with a "stream" or undefined RECORD_TYPE (support not planned)
  - RSS PostScript files from both Raw Data and Science Data Products (support not planned)
- MRO
  - RSS .tnf (support not planned)
- MSL
  - Malin Space Science Systems (MSSS) Camera EDRs: "Raw" (EDR) data from the
    Mars Science Laboratory's MSSS-produced cameras (Mastcam, MAHLI, and
    MARDI), are archived in a bespoke compressed format. These images carry
    the extension '.DAT'. Software for converting these files to PDS3-style
    uncompressed raster .IMG files exists in the archive. We plan to either include / compile this code with the installation of this package or (much better) to port `dat2img` to pure
    Python. Help is welcomed with either of these efforts! The MSL
    "calibrated" (RDR) files for these cameras are not compressed in this way.
  - ChemCam LIBS EDR tables (support not planned)
- Pioneer Venus Orbiter
  - ORPA raw data (support not planned)
  - ORSE ODRs (support not planned)
- Rosetta
  - Orbiter:
    - MIDAS RDRs with .dat file extension (support planned)
    - VIRTIS RDRs (support planned)
    - VIRTIS geometry data
  - Lander:
    - CONSERT EDRs, RDRs, and REFDRs (support planned)
    - SD2 EDRs (support not planned)
- Vega 1 and 2
  - PUMA raw and processed data (support not planned)
  - PUMA mode data (support planned)
