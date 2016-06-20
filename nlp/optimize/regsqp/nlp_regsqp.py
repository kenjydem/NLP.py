#!/usr/bin/env python
# -*- coding: utf-8 -*-
import logging
import sys
import os
from argparse import ArgumentParser

from nlp.model.pysparsemodel import PySparseAmplModel
from nlp.tools.logs import config_logger


def regsqp_stats(regsqp):
    """Obtain RegSQP statistics and indicate failures with negatives."""
    if regsqp.short_status in ("opt"):
        it = regsqp.itn
        fc, gc = regsqp.model.obj.ncalls, regsqp.model.grad.ncalls
        hc = regsqp.model.hess.ncalls
        jprod = regsqp.model.jprod.ncalls + regsqp.model.jtprod.ncalls
        cn = regsqp.cnorm
        gLn = regsqp.gLnorm
        ts = regsqp.tsolve
    else:
        it = -regsqp.itn
        fc, gc = -regsqp.model.obj.ncalls, -regsqp.model.grad.ncalls
        hc = -regsqp.model.hess.ncalls
        jprod = -(regsqp.model.jprod.ncalls + regsqp.model.jtprod.ncalls)
        cn = -1.0 if regsqp.cnorm is None else -regsqp.cnorm
        gLn = -1.0 if regsqp.gLnorm is None else -regsqp.gLnorm
        ts = -1.0 if regsqp.tsolve is None else -regsqp.tsolve
    return (it, fc, gc, hc, jprod, cn, gLn, ts)


desc = "Regularized SQP method for equality-constrained problems based."
desc += "By default, exact second derivatives are used."

# Define allowed command-line options
parser = ArgumentParser(description=desc)

parser.add_argument("-a", "--abstol", action="store", type=float,
                    default=1.0e-7, dest="abstol",
                    help="Absolute stopping tolerance")
parser.add_argument("-r", "--reltol", action="store", type=float,
                    default=1.0e-6, dest="reltol",
                    help="Absolute stopping tolerance")
parser.add_argument("-t", "--theta", action="store", type=float,
                    default=0.99, dest="theta",
                    help="Sufficient improvement factor in outer iterations")
parser.add_argument("-p", "--pairs", type=int,
                    default=6, dest="npairs", help="quasi-Newton memory")
parser.add_argument("-q", "--quasi_newton", action="store_true",
                    default=False, dest="quasi_newton",
                    help="use L-BFGS approximations of second derivatives")
parser.add_argument("-i", "--iter", action="store", type=int, default=1000,
                    dest="maxiter", help="maximum number of iterations")

# Parse command-line arguments
(args, other) = parser.parse_known_args()

# Translate options to input arguments.
opts = {}

if args.quasi_newton:
    from new_regsqp_BFGS import RegSQPBFGSIterativeSolver as RegSQP
else:
    from new_regsqp import RegSQPSolver as RegSQP

nprobs = len(other)
if nprobs == 0:
    raise ValueError("Please supply problem name as argument")

# Create root logger.
log = config_logger('nlp', '%(name)-3s %(levelname)-5s %(message)s')

# Configure the solver logger.
reg_logger = config_logger("nlp.regsqp",
                           "%(name)-8s %(levelname)-5s %(message)s",
                           level=logging.WARN if nprobs > 1 else logging.DEBUG)

log.info('%12s %5s %5s %6s %8s %8s %8s %6s %6s %6s %5s %7s',
         'name', 'nvar', 'ncons', 'iter', 'f', u'‖c‖', u'‖∇L‖',
         '#f', '#g', '#jprod', 'stat', 'time')

# Solve each problem in turn.
for problem in other:
    verbose = True

    model = PySparseAmplModel(problem, **opts)

    prob_name = os.path.basename(problem)
    if prob_name[-3:] == '.nl':
        prob_name = prob_name[:-3]

    # Check for equality-constrained problem.
    n_ineq = model.nlowerC + model.nupperC + model.nrangeC
    if model.nbounds > 0 or n_ineq > 0 or model.nequalC == 0:
        msg = '%s has %d bounds and %d inequality constraints\n'
        log.error(msg, model.name, model.nbounds, n_ineq)
        verbose = False
        continue

    # model.compute_scaling_cons()

    regsqp = RegSQP(model, maxiter=args.maxiter, theta=args.theta)

    try:
        regsqp.solve()
        status = regsqp.short_status
    except:
        msg = sys.exc_info()[1].message
        status = msg if len(msg) > 0 else "xfail"  # unknown failure
    niter, fcalls, gcalls, hcalls, jprod, cnorm, gLn, tsolve = regsqp_stats(
        regsqp)

    log.info("%12s %5d %5d %6d %8.1e %8.1e %8.1e %6d %6d %6d %5s %7.3f",
             model.name, model.nvar, model.m, niter, regsqp.f, cnorm, gLn,
             fcalls, gcalls, jprod, status, tsolve)

if nprobs == 1 and verbose:
    print regsqp.x
    # Output final statistics
    log.info('--------------------------------')
    log.info('regsqp: End of Execution')
    log.info('  Problem                      : %-s', prob_name)
    log.info('  Number of variables          : %-d', regsqp.model.n)
    log.info('  Number of linear constraints : %-d', regsqp.model.nlin)
    log.info('  Number of general constraints: %-d',
             regsqp.model.m - regsqp.model.nlin)
    log.info('  Initial/Final Objective      : %-g/%-g', regsqp.f0, regsqp.f)
    log.info('  Number of iterations         : %-d', niter)

    log.info('         inner iterations      : %-d', regsqp.inner_itn)
    log.info('  Number of function evals     : %-d', fcalls)
    log.info('  Number of gradient evals     : %-d', gcalls)
    log.info('  Number of Jacobian evals     : %-d',
             0 if args.quasi_newton else gcalls)
    log.info('  Number of Jacobian products  : %-d',
             jprod if args.quasi_newton else 0)
    log.info('  Number of Hessian evals      : %-d',
             0 if args.quasi_newton else hcalls)
    log.info('  Solve time                   : %-gs', tsolve)
    log.info('--------------------------------')
