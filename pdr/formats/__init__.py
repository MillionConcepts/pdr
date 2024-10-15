"""
This module implements a wide variety of special-case behaviors for
nonconforming or malformatted data products. It implements these behaviors as
functions in distinct submodules organized by 'dataset' (mission, instrument,
etc.); the `checkers` submodule contains dispatch functions that preempt
generic behaviors and redirect them to functions from one of the dataset
submodules. See the documentation for `checkers` for details on this behavior.
"""

from .checkers import *
import pdr.formats.cassini as cassini
import pdr.formats.clementine as clementine
import pdr.formats.dawn as dawn
import pdr.formats.diviner as diviner
import pdr.formats.epoxi as epoxi
import pdr.formats.galileo as galileo
import pdr.formats.ground as ground
import pdr.formats.ihw as ihw
import pdr.formats.iue as iue
import pdr.formats.juno as juno
import pdr.formats.lroc as lroc
import pdr.formats.lro as lro
import pdr.formats.mariner as mariner
import pdr.formats.mer as mer
import pdr.formats.mex as mex
import pdr.formats.mgn as mgn
import pdr.formats.mgs as mgs
import pdr.formats.mro as mro
import pdr.formats.msl_apxs as msl_apxs
import pdr.formats.msl_cmn as msl_cmn
import pdr.formats.msl_ccam as msl_ccam
import pdr.formats.msl_places as msl_places
import pdr.formats.msl_rems as msl_rems
import pdr.formats.nh as nh
import pdr.formats.odyssey as odyssey
import pdr.formats.phoenix as phoenix
import pdr.formats.pvo as pvo
import pdr.formats.rosetta as rosetta
import pdr.formats.saturn_rpx as saturn_rpx
import pdr.formats.themis as themis
import pdr.formats.ulysses as ulysses
import pdr.formats.vega as vega
import pdr.formats.viking as viking
import pdr.formats.voyager as voyager
