"""Python interface to the AMPL modeling language.

.. moduleauthor:: M. P. Friedlander <mpf@cs.ubc.ca>
.. moduleauthor:: D. Orban <dominique.orban@gerad.ca>
"""
try:
    from nlp.model import _amplmodel
except ImportError:
    raise

import numpy as np
from nlp.model.nlpmodel import NLPModel
from nlp.model.qnmodel import QuasiNewtonModel
from pykrylov.linop import CoordLinearOperator
from nlp.tools import sparse_vector_class as sv

import tempfile
import os

__docformat__ = 'restructuredtext'


def GenTemplate(model, data=None, opts=None):
    """
    Write out an Ampl template file,
    using files model.mod and data.dat (if available).
    The template will be given a temporary name.
    """
    # Create a temporary template file and write in a header.
    tmpname = tempfile.mktemp()
    template = open(tmpname, 'w')
    template.write("# Template file for %s.\n" % model)
    template.write("# Automatically generated by AmplPy.\n")

    # Later we can use opts to hold a list of Ampl options, eg,
    #   option presolve 0;
    # that can be written into the template file.
    if opts is not None:
        pass

    # Template file body.
    if model[-4:] == '.mod':
        model = model[:-4]
    template.write("model %s.mod;\n" % model)

    if data is not None:
        if data[-4:] == '.dat':
            data = data[:-4]
        template.write("data  %s.dat;\n" % data)
    template.write("write g%s;\n" % model)

    # Finish off the template file.
    template.close()

    # We'll need to know the template file name.
    return tmpname


def writestub(template):
    os.system("ampl %s" % template)


class AmplModel(NLPModel):
    """
    AmplModel creates an instance of an AMPL model. If the `nl` file is
    already available, simply call `AmplModel(stub)` where the string
    `stub` is the name of the model. For instance: `AmplModel('elec')`.
    If only the `.mod` file is available, set the positional parameter
    `neednl` to `True` so AMPL generates the `nl` file, as in
    `AmplModel('elec.mod', data='elec.dat', neednl=True)`.

    Among important attributes of this class are :attr:`nvar`, the number of
    variables, :attr:`ncon`, the number of constraints, and :attr:`nbounds`,
    the number of variables subject to at least one bound constraint.
    """

    def __init__(self, stub, **kwargs):

        data = kwargs.get('data', None)
        opts = kwargs.get('opts', None)

        if stub[-4:] == '.mod':
            # Create the nl file.
            template = GenTemplate(stub, data, opts)
            writestub(template)
            stub = stub[:-4]

        # Initialize the ampl module
        try:
            model = self.model = _amplmodel.ampl(stub)
        except:
            raise ValueError('Cannot initialize model %s' % stub)

        super(AmplModel, self).__init__(model.n_var, model.n_con,
                                        name=kwargs.get('name', stub),
                                        x0=model.get_x0(),
                                        pi0=model.get_pi0(),
                                        Lvar=model.get_Lvar(),
                                        Uvar=model.get_Uvar(),
                                        Lcon=model.get_Lcon(),
                                        Ucon=model.get_Ucon())

        # Get basic info on problem
        self.minimize = (model.objtype == 0)
        (self._lin, self._nln, self._net) = model.get_CType()  # Constr. types
        # Constraint types
        (self._lin, self._nln, self._net) = model.get_CType()
        self._nlin = len(self.lin)       # number of linear  constraints
        self._nnln = len(self.nln)       # ...       nonlinear   ...
        self._nnet = len(self.net)       # ...       network   ...

        self._sparse_coord = True       # Sparse matrices in coord format

        # Get sparsity info
        self.nnzj = model.get_nnzj()    # number of nonzeros in Jacobian
        self.nnzh = model.get_nnzh()    # ...                   Hessian

        # Initialize scaling attributes
        self.scale_obj = None   # Objective scaling
        self.scale_con = None   # Constraint scaling

    def __del__(self):
        self.model._dealloc()

    def writesol(self, x, z, msg):
        """Write primal-dual solution and message msg to `stub.sol`."""
        return self.model.ampl_sol(x, z, msg)

    def get_pi0(self):
        return self.model.pi0()

    def obj(self, x, obj_num=0):
        """Evaluate objective function value at x.

        Returns a floating-point number. This method changes the sign of the
        objective value if the problem is a maximization problem.
        """

        # AMPL doesn't exactly exit gracefully if obj_num is out of range.
        if obj_num < 0 or obj_num >= self.model.n_obj:
            raise ValueError('Objective number is out of range.')

        f = self.model.eval_obj(x)
        if self.scale_obj:
            f *= self.scale_obj
        if not self.minimize:
            f *= -1
        return f

    def grad(self, x, obj_num=0):
        """Evaluate objective gradient at x.

        Returns a Numpy array. This method changes the sign of the objective
        gradient if the problem is a maximization problem.
        """

        # AMPL doesn't exactly exit gracefully if obj_num is out of range.
        if obj_num < 0 or obj_num >= self.model.n_obj:
            raise ValueError('Objective number is out of range.')

        g = self.model.grad_obj(x)
        if self.scale_obj:
            g *= self.scale_obj
        if not self.minimize:
            g *= -1
        return g

    def sgrad(self, x):
        """Evaluate sparse objective gradient at x.

        Returns a sparse vector. This method changes the sign of the objective
        gradient if the problem is a maximization problem.
        """
        sg = sv.SparseVector(self.n, self.model.eval_sgrad(x))
        if self.scale_obj:
            sg *= self.scale_obj
        if not self.minimize:
            sg *= -1
        return sg

    def cost(self):
        """Evaluate sparse cost vector.

        Useful when problem is a linear program.
        Return a sparse vector. This method changes the sign of the cost vector
        if the problem is a maximization problem.
        """
        sc = sv.SparseVector(self.n, self.model.eval_cost())
        if self.scale_obj:
            sc *= self.scale_obj
        if not self.minimize:
            sc *= -1
        return sc

    def cons(self, x):
        """Evaluate vector of constraints at x.

        Returns a Numpy array.
        The constraints appear in natural order. To order them as follows

        1. equalities
        2. lower bound only
        3. upper bound only
        4. range constraints,

        use the `permC` permutation vector.
        """
        c = self.model.eval_cons(x)
        if self.scale_con is not None:
            c *= self.scale_con
        return c

    def icons(self, i, x):
        """Evaluate value of i-th constraint at x.

        Returns a floating-point number.
        """
        ci = self.model.eval_ci(i, x)
        if self.scale_con is not None:
            ci *= self.scale_con[i]
        return ci

    def igrad(self, i, x):
        """Evaluate dense gradient of i-th constraint at x.

        Returns a Numpy array.
        """
        gi = self.model.eval_gi(i, x)
        if self.scale_con is not None:
            gi *= self.scale_con[i]
        return gi

    def sigrad(self, i, x):
        """Evaluate sparse gradient of i-th constraint at x.

        Returns a sparse vector representing the sparse gradient
        in coordinate format.
        """
        sci = sv.SparseVector(self.n, self.model.eval_sgi(i, x))
        if self.scale_con is not None:
            sci *= self.scale_con[i]
        return sci

    def irow(self, i):
        """Evaluate sparse gradient of the linear part of the i-th constraint.

        Useful to obtain constraint rows when problem
        is a linear programming problem.
        """
        sri = sv.SparseVector(self.n, self.model.eval_row(i))
        if self.scale_con is not None:
            sri *= self.scale_con[i]
        return sri

    def A(self, *args, **kwargs):
        """Evaluate sparse Jacobian of the linear part of the constraints.

        Useful to obtain constraint matrix when problem
        is a linear programming problem.
        """
        store_zeros = kwargs.get('store_zeros', False)
        store_zeros = 1 if store_zeros else 0
        vals, rows, cols = self.model.eval_A(store_zeros)
        if self.scale_con is not None:
            vals *= self.scale_con[rows]
        return (vals, rows, cols)

    def jac(self, x, *args, **kwargs):
        """Evaluate sparse Jacobian of constraints at x.

        Returns a sparse matrix in coordinate format.
        """
        store_zeros = kwargs.get('store_zeros', False)
        store_zeros = 1 if store_zeros else 0
        vals, rows, cols = self.model.eval_J(x, store_zeros)
        if self.scale_con is not None:
            vals *= self.scale_con[rows]
        return (vals, rows, cols)

    def jac_pos(self, x, **kwargs):
        """
        Convenience function to evaluate the Jacobian matrix of the constraints
        reformulated as

          ci(x) = ai     for i in equalC
          ci(x) - Li >= 0  for i in lowerC
          ci(x) - Li >= 0  for i in rangeC
          Ui - ci(x) >= 0  for i in upperC
          Ui - ci(x) >= 0  for i in rangeC.

        The gradients of the general constraints appear in 'natural' order,
        i.e., in the order in which they appear in the problem. The gradients
        of range constraints appear in two places: first in the 'natural'
        location and again after all other general constraints, with a flipped
        sign to account for the upper bound on those constraints.

        The overall Jacobian of the new constraints thus has the form

        [ J ]
        [-JR]

        This is a `(m + nrangeC)`-by-`n` matrix, where `J` is the Jacobian
        of the general constraints in the order above in which the sign of
        the 'less than' constraints is flipped, and `JR` is the Jacobian of
        the 'less than' side of range constraints.
        """
        store_zeros = kwargs.get('store_zeros', False)
        store_zeros = 1 if store_zeros else 0
        n = self.n
        m = self.m
        nrangeC = self.nrangeC
        upperC = self.upperC
        rangeC = self.rangeC

        # BROKEN
        # Initialize sparse Jacobian
        # J = BlockLinearOperator([[self.jop(x)],
        #                         [ReducedLinearOperator(self.jop(x))]])
        # Insert contribution of general constraints
        J[:m, :n] = self.jac(x, **kwargs)
        J[upperC, :n] *= -1        # Flip sign of 'upper' gradients.
        J[m:, :n] = -J[rangeC, :n]   # Append 'upper' side of range const.
        return J

    # Implement jop because AMPL models don't define jprod / jtprod.
    def jop(self, x, *args, **kwargs):
        """Jacobian at x as a linear operator."""
        vals, rows, cols = self.jac(x, *args, **kwargs)
        return CoordLinearOperator(vals, rows, cols,
                                   nargin=self.nvar,
                                   nargout=self.ncon,
                                   symmetric=False)

    def jprod(self, x, p, **kwargs):
        """Evaluate Jacobian-vector product at x with p."""
        return self.jop(x, **kwargs) * p

    def jtprod(self, x, p, **kwargs):
        """Evaluate transposed-Jacobian-vector product at x with p."""
        return self.jop(x, **kwargs).T * p

    def hess(self, x, z=None, obj_num=0, *args, **kwargs):
        """Evaluate Hessian.

        Evaluate sparse lower triangular Lagrangian Hessian at (x, z).
        By convention, the Lagrangian has the form L = f - c'z.
        """
        obj_weight = kwargs.get('obj_weight', 1.0)
        store_zeros = kwargs.get('store_zeros', False)
        store_zeros = 1 if store_zeros else 0
        if z is None:
            z = np.zeros(self.m)

        if self.scale_obj:
            obj_weight *= self.scale_obj
        if self.scale_con:
            z = z.copy()
            z *= self.scale_con

        vals, rows, cols = self.model.eval_H(x, z, obj_weight, store_zeros)

        if not self.minimize:
            vals *= -1
        return (vals, rows, cols)

    def hprod(self, x, z, v, **kwargs):
        """Hessian-vector product.

        Evaluate matrix-vector product H(x,z) * v, where H is the Hessian of
        the Lagrangian evaluated at the primal-dual pair (x,z).
        Zero multipliers can be specified as an array of zeros or as `None`.

        Returns a Numpy array.

        Bug: x is ignored, and is determined as the point at which the
        objective or gradient were last evaluated.

        :keywords:
          :obj_weight: Add a weight to the Hessian of the objective function.
                 By default, the weight is one. Setting it to zero
                 allows to exclude the Hessian of the objective from
                 the Hessian of the Lagrangian.
        """
        obj_weight = kwargs.get('obj_weight', 1.0)
        if z is None:
            z = np.zeros(self.m)

        if self.scale_obj:
            obj_weight *= self.scale_obj
        if self.scale_con:
            z = z.copy()
            z *= self.scale_con

        Hv = self.model.H_prod(x, z, v, obj_weight)
        if not self.minimize:
            Hv *= -1
        return Hv

    def hiprod(self, x, i, v, **kwargs):
        """Constraint Hessian-vector product.

        Returns a Numpy array.
        Bug: x is ignored. See hprod above.
        """
        z = np.zeros(self.m)
        z[i] = -1
        Hv = self.model.H_prod(x, z, v, 0.)
        if self.scale_con is not None:
            Hv *= self.scale_con[i]
        return Hv

    def ghivprod(self, x, g, v, **kwargs):
        """Evaluate individual dot products (g, Hi(x)*v).

        Evaluate the vector of dot products (g, Hi(x)*v) where Hi(x) is the
        Hessian of the i-th constraint at point x, i=1..m.
        """
        if self.nnln == 0:       # Quick exit if no nonlinear constraints
            return np.zeros(self.m)
        gHi = self.model.gHi_prod(x, g, v)
        if self.scale_con is not None:
            gHi *= self.scale_con  # componentwise product
        return gHi

    def islp(self):
        """Determine whether problem is a linear programming problem."""
        if self.model.nlo or self.model.nlc or self.model.nlnc:
            return False
        return True

    def set_x(self, x):
        """Freeze independent variables.

        Set `x` as current value for subsequent calls
        to :meth:`obj`, :meth:`grad`, :meth:`jac`, etc. If several
        of :meth:`obj`, :meth:`grad`, :meth:`jac`, ..., will be called with the
        same argument `x`, it may be more efficient to first call `set_x(x)`.
        In AMPL, :meth:`obj`, :meth:`grad`, etc., normally check whether their
        argument has changed since the last call. Calling `set_x()` skips this
        check.

        See also :meth:`unset_x`.
        """
        return self.model.set_x(x)

    def unset_x(self):
        """Release independent variables.

        Reinstates the default behavior of :meth:`obj`, :meth:`grad`, `jac`,
        etc., which is to check whether their argument has changed since the
        last call.

        See also :meth:`set_x`.
        """
        return self.model.unset_x()

    def display_basic_info(self):
        """Display vital statistics about the current model."""
        super(AmplModel, self).display_basic_info()

        # Display info that wasn't available in NLPModel.
        write = self.logger.info
        write('Number of nonzeros in Jacobian: %d\n' % self.nnzj)
        write('Number of nonzeros in Lagrangian Hessian: %d\n' % self.nnzh)
        if self.islp():
            write('This problem is a linear program.\n')

        return


class QNAmplModel(QuasiNewtonModel, AmplModel):
    """AMPL model with quasi-Newton Hessian approximation."""
    pass  # All the work is done by the parent classes.
