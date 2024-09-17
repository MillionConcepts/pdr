from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import os
from posixpath import join as urljoin


class PDS4ToolsTestCase(object):

    # Path to local data directory
    local_data_dir = os.path.join(os.path.dirname(__file__), 'data')

    # Path to remote data directory
    web_data_dir = 'https://raw.githubusercontent.com/Small-Bodies-Node/pds4_tools/master/pds4_tools/tests/data/'

    # Retrieve data locally or from web
    @classmethod
    def data(cls, filename, from_web=False):

        if from_web:
            path_join_func = urljoin
            data_dir = cls.web_data_dir

        else:
            path_join_func = os.path.join
            data_dir = cls.local_data_dir

        return path_join_func(data_dir, filename)
