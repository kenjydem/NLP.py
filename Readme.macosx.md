# Build instructions for Mac OS/X users

If you require one of ASL, `pyadolc`, `pycppad`, MUMPS, qr_mumps or SuiteSparse, installing `NLP.py` will be much easier if you use [Homebrew](https://brew.sh).
Follow the instructions to install Homebrew and import the *science* formulas:
```bash
brew tap homebrew/science
```

## Requirements

Install `numpy` and `PyKrylov`:
```bash
pip install -q numpy
pip install -q git+https://github.com/PythonOptimizers/pykrylov.git@develop
```

## Optional Dependencies

### Sparse Matrix Storage

#### CySparse

```bash
pip install -q git+https://github.com/PythonOptimizers/cysparse.git
```

#### PySparse

```bash
pip install -q git+https://github.com/optimizers/pysparse.git
```

### SciPy

```bash
pip install -q scipy
```

### Derivatives Computation

#### ASL

The ASL will allow [AMPL](http://www.ampl.com) models to be loaded in `NLP.py` after they have been decoded to a `.nl` file.
Creating the `.nl` file for anything else than small models requires an AMPL license.
A few sample `.nl` files are included with `NLP.py`.
The ASL will compute sparse first and second derivatives.

The ASL may be installed from Homebrew:
```bash
brew install asl
```
Specify the location of the ASL in `setup.cfg`:
```bash
echo "[ASL]" > site.cfg
echo "asl_dir = $(brew --prefix asl)" >> site.cfg
```

#### ADOL-C

ADOL-C will allow models to be coded up directly in Python and sparse first and second derivatives to be computed via automatic differentiation.
This is the preferred way to model large-scale problems in Python.
First install ADOL-C:
```bash
brew install adol-c  # will also install Colpack
brew install boost-python
```
Then install `pyadolc`:
```bash
cd $HOME  # or another local
git clone https://github.com/b45ch1/pyadolc.git && cd pyadolc
python setup.py install  # press [Enter] when prompted
```

#### CppAD

CppAD will allow models to be coded up directly in Python and *dense* first and second derivatives to be computed via automatic differentiation.

First install CppAD:
```bash
brew install cppad [--with-adol-c] --with-openmp
```
Then install `pycppad`:
```bash
pip install -q git+https://github.com/b45ch1/pycppad.git
```

#### AlgoPy

AlgoPy will allow models to be coded up directly in Python and *dense* first and second derivatives to be computed via automatic differentiation.

```bash
pip install -q algopy
```

### Factorizations

#### HSL.py

Follow instructions at https://github.com/PythonOptimizers/HSL.py

#### MUMPS.py

Follow instructions at https://github.com/PythonOptimizers/MUMPS.py

#### qr_mumps.py

Follow instructions at https://github.com/PythonOptimizers/qr_mumps.py

#### SuiteSparse.py

Follow instructions at https://github.com/PythonOptimizers/SuiteSparse.py

## Troubleshooting

If you encounter build errors while installing `pyadolc`, edit and change `setup.py` as follows:
```diff
diff --git a/setup.py b/setup.py
index 5e6e695..68f5c68 100644
--- a/setup.py
+++ b/setup.py
@@ -36,7 +36,7 @@ colpack_lib_path1    = os.path.join(COLPACK_DIR, 'lib')
 colpack_lib_path2    = os.path.join(COLPACK_DIR, 'lib64')

 # ADAPT THIS TO FIT YOUR SYSTEM
-extra_compile_args = ['-std=c++11 -ftemplate-depth-100 -DBOOST_PYTHON_DYNAMIC_LIB']
+extra_compile_args = ['-std=c++11 -stdlib=libc++ -mmacosx-version-min=10.9 -ftemplate-depth-100 -DBOOST_PYTHON_DYNAMIC_LIB']
 include_dirs = [get_numpy_include_dirs()[0], boost_include_path, adolc_include_path, colpack_include_path]
 library_dirs = [boost_library_path1, boost_library_path2, adolc_library_path1, adolc_library_path2, colpack_lib_path1, colpack_lib_path2]
 libraries = ['boost_python','adolc', 'ColPack']
```
