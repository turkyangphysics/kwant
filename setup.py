#!/usr/bin/env python

CONFIG_FILE = 'build.conf'
STATIC_VERSION_FILE = 'kwant/_static_version.py'
REQUIRED_CYTHON_VERSION = (0, 17, 1)
MUMPS_DEBIAN_PACKAGE = 'libmumps-scotch-dev'
NO_CYTHON_OPTION = '--no-cython'
TUT_DIR = 'tutorial'
TUT_GLOB = 'doc/source/tutorial/*.py'
TUT_HIDDEN_PREFIX = '#HIDDEN'

import sys
import os
import glob
import subprocess
import ConfigParser
from distutils.core import setup, Command
from distutils.extension import Extension
from distutils.errors import DistutilsError, CCompilerError
from distutils.command.build import build as distutils_build
from distutils.command.sdist import sdist as distutils_sdist
import numpy

try:
    import Cython
except:
    cython_version = ()
else:
    cython_version = tuple(
        int(n) for n in Cython.__version__.split('-')[0].split('.'))

try:
    sys.argv.remove(NO_CYTHON_OPTION)
    cythonize = False
except ValueError:
    cythonize = True

if cythonize and cython_version:
    from Cython.Distutils import build_ext
else:
    from distutils.command.build_ext import build_ext


class kwant_build_ext(build_ext):
    def run(self):
        try:
            build_ext.run(self)
        except (DistutilsError, CCompilerError):
            print >>sys.stderr, \
"""{0}
The compilation of kwant has failed.  Please examine the error message
above and consult the installation instructions in README.
You might have to customize {1}.
{0}
Build configuration was:
{2}
{0}""".format('*' * 70, CONFIG_FILE, build_summary)
            raise
        print '**************** Build summary ****************'
        print build_summary


class build_tut(Command):
    description = "build the tutorial scripts"
    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        if not os.path.exists(TUT_DIR):
            os.mkdir(TUT_DIR)
        for in_fname in glob.glob(TUT_GLOB):
            out_fname = os.path.join(TUT_DIR, os.path.basename(in_fname))
            with open(in_fname) as in_file:
                with open(out_fname, 'w') as out_file:
                    for line in in_file:
                        if not line.startswith(TUT_HIDDEN_PREFIX):
                            out_file.write(line)


# Our version of the "build" command also makes sure the tutorial is made.
# Even though the tutorial is not necessary for installation, and "build" is
# supposed to make everything needed to install, this is a robust way to ensure
# that the tutorial is present.
class kwant_build(distutils_build):
    sub_commands = [('build_tut', None)] + distutils_build.sub_commands
    pass


# Make the command "sdist" depend on "build".  This verifies that the
# distribution in the current state actually builds.  It also makes sure that
# the Cython-made C files and the tutorial will be included in the source
# distribution and that they will be up-to-date.
class kwant_sdist(distutils_sdist):
    sub_commands = [('build', None)] + distutils_sdist.sub_commands
    pass


# This is an exact copy of the function from kwant/version.py.  We can't import
# it here (because kwant is not yet built when this scipt is run), so we just
# include a copy.
def get_version_from_git():
    kwant_dir = os.path.dirname(os.path.abspath(__file__))
    try:
        p = subprocess.Popen(['git', 'describe'], cwd=kwant_dir,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except OSError:
        return

    if p.wait() != 0:
        return
    version = p.communicate()[0].strip()

    if version[0] == 'v':
        version = version[1:]

    try:
        p = subprocess.Popen(['git', 'diff', '--quiet'], cwd=kwant_dir)
    except OSError:
        version += '-confused'  # This should never happen.
    else:
        if p.wait() == 1:
            version += '-dirty'
    return version


def get_static_version():
    """Return the version as recorded inside kwant."""
    try:
        with open(STATIC_VERSION_FILE) as f:
            contents = f.read()
            assert contents[:11] == "version = '"
            assert contents[-2:] == "'\n"
            return contents[11:-2]
    except:
        return None


def version():
    """Determine the version of kwant.  Return it and save it in a file."""
    git_version = get_version_from_git()
    static_version = get_static_version()
    if git_version is not None:
        version = git_version
        if static_version != git_version:
            with open(STATIC_VERSION_FILE, 'w') as f:
                f.write("version = '%s'\n" % version)
    elif static_version is not None:
        version = static_version
    else:
        version = 'unknown'
    return version


def debian_mumps():
    """Return the configuration for debian-provided MUMPS if it is available,
    or an empty dictionary otherwise."""
    try:
        p = subprocess.Popen(
            ['dpkg-query', '-W', '-f=${Status}', MUMPS_DEBIAN_PACKAGE],
            stdout=subprocess.PIPE)
    except OSError:
        pass
    else:
        if p.wait() == 0 and p.communicate()[0] == 'install ok installed':
            return {'libraries': ['zmumps_scotch', 'mumps_common_scotch',
                                  'pord', 'mpiseq_scotch', 'gfortran']}
    return {}


def extensions():
    """Return a list of tuples (args, kwrds) to be passed to
    Extension. possibly after replacing ".pyx" with ".c" if Cython is not to be
    used."""

    global build_summary
    build_summary = []

    #### Add components of kwant without external compile-time dependencies.
    result = [
        (['kwant._system', ['kwant/_system.pyx']],
         {'include_dirs': ['kwant/graph']}),
        (['kwant.graph.core', ['kwant/graph/core.pyx']],
         {'depends': ['kwant/graph/core.pxd', 'kwant/graph/defs.h',
                      'kwant/graph/defs.pxd']}),
        (['kwant.graph.utils', ['kwant/graph/utils.pyx']],
         {'depends': ['kwant/graph/defs.h', 'kwant/graph/defs.pxd',
                      'kwant/graph/core.pxd']}),
        (['kwant.graph.slicer', ['kwant/graph/slicer.pyx',
                                 'kwant/graph/c_slicer/partitioner.cc',
                                 'kwant/graph/c_slicer/slicer.cc']],
         {'depends': ['kwant/graph/defs.h', 'kwant/graph/defs.pxd',
                      'kwant/graph/core.pxd',
                      'kwant/graph/c_slicer.pxd',
                      'kwant/graph/c_slicer/bucket_list.h',
                      'kwant/graph/c_slicer/graphwrap.h',
                      'kwant/graph/c_slicer/partitioner.h',
                      'kwant/graph/c_slicer/slicer.h']})]

    #### Add components of kwant with external compile-time dependencies.
    config = ConfigParser.ConfigParser()
    try:
        with open(CONFIG_FILE) as f:
            config.readfp(f)
    except IOError:
        with open(CONFIG_FILE, 'w') as f:
            f.write('# Created by setup.py - feel free to modify.\n')

    kwrds_by_section = {}
    for section in config.sections():
        kwrds_by_section[section] = kwrds = {}
        for name, value in config.items(section):
            kwrds[name] = value.split()

    # Setup LAPACK.
    lapack = kwrds_by_section.get('lapack')
    if lapack:
        build_summary.append('User-configured LAPACK and BLAS')
    else:
        lapack = {'libraries': ['lapack', 'blas']}
        build_summary.append('Default LAPACK and BLAS')
    kwrds = lapack.copy()
    kwrds.setdefault('depends', []).extend(
        [CONFIG_FILE, 'kwant/linalg/f_lapack.pxd'])
    result.append((['kwant.linalg.lapack', ['kwant/linalg/lapack.pyx']],
                   kwrds))

    # Setup MUMPS.
    kwrds = kwrds_by_section.get('mumps')
    if kwrds:
        build_summary.append('User-configured MUMPS')
    else:
        kwrds = debian_mumps()
        if kwrds:
            build_summary.append(
                'MUMPS from package {0}'.format(MUMPS_DEBIAN_PACKAGE))
    if kwrds:
        for name, value in lapack.iteritems():
            kwrds.setdefault(name, []).extend(value)
        kwrds.setdefault('depends', []).extend(
            [CONFIG_FILE, 'kwant/linalg/cmumps.pxd'])
        result.append((['kwant.linalg._mumps', ['kwant/linalg/_mumps.pyx']],
                       kwrds))
    else:
        build_summary.append('No MUMPS support')

    build_summary = '\n'.join(build_summary)
    return result


def ext_modules(extensions):
    """Prepare the ext_modules argument for distutils' setup."""
    result = []
    for args, kwrds in extensions:
        if not cythonize or not cython_version:
            if 'language' in kwrds:
                if kwrds['language'] == 'c':
                    ext = '.c'
                elif kwrds['language'] == 'c++':
                    ext = '.cpp'
                else:
                    print >>sys.stderr, 'Unknown language'
                    exit(1)
            else:
                ext = '.c'
            pyx_files = []
            cythonized_files = []
            sources = []
            for f in args[1]:
                if f[-4:] == '.pyx':
                    pyx_files.append(f)
                    f = f[:-4] + ext
                    cythonized_files.append(f)
                sources.append(f)
            args[1] = sources

            try:
                cythonized_oldest = min(os.stat(f).st_mtime
                                        for f in cythonized_files)
            except OSError:
                print >>sys.stderr, \
                    "Error: Cython-generated file {0} is missing.".format(f)
                if cythonize:
                    print >>sys.stderr, "Install Cython so it can be made" \
                    " or use a source distribution of kwant."
                else:
                    print >>sys.stderr, "Run setup.py without", \
                        NO_CYTHON_OPTION
                exit(1)
            for f in pyx_files + kwrds.get('depends', []):
                if os.stat(f).st_mtime > cythonized_oldest:
                    msg = "Warning: {0} is newer than its source file, "
                    if cythonize:
                        msg += "but Cython is not installed."
                    else:
                        msg += "but Cython is not to be run."
                    print >>sys.stderr, msg.format(f)

        result.append(Extension(*args, **kwrds))

    return result


def main():
    if cythonize and cython_version < REQUIRED_CYTHON_VERSION:
        msg = 'Warning: Cython {0} is required but '
        if cython_version:
            msg += 'only {1} is present.'
        else:
            msg += 'it is not installed.'
        print >>sys.stderr, msg.format(
            '.'.join(str(e) for e in REQUIRED_CYTHON_VERSION),
            '.'.join(str(e) for e in cython_version))

    setup(name='kwant',
          version=version(),
          author='A. R. Akhmerov, C. W. Groth, X. Waintal, M. Wimmer',
          author_email='christoph.groth@cea.fr',
          description="A package for numerical "
          "quantum transport calculations.",
          license="not to be distributed",
          packages=["kwant", "kwant.graph", "kwant.linalg", "kwant.physics",
                    "kwant.solvers"],
          cmdclass={'build': kwant_build,
                    'sdist': kwant_sdist,
                    'build_ext': kwant_build_ext,
                    'build_tut': build_tut},
          ext_modules=ext_modules(extensions()),
          include_dirs=[numpy.get_include()])

if __name__ == '__main__':
    main()
