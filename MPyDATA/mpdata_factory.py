"""
Created at 21.10.2019

@author: Piotr Bartman
@author: Michael Olesik
@author: Sylwester Arabas
"""

import numpy as np

from .arakawa_c.vector_field import VectorField
from .arakawa_c.scalar_field import ScalarField
from .eulerian_fields import EulerianFields
from .mpdata import MPDATA
from .options import Options
from MPyDATA.factories.step import make_step
from .arakawa_c.discretisation import nondivergent_vector_field_2d, discretised_analytical_solution
from .arakawa_c.boundary_condition.extrapolated import Extrapolated
from .arakawa_c.boundary_condition.zero import Zero


class MPDATAFactory:
    @staticmethod
    def n_halo(opts: Options):
        if opts.divergent_flow or opts.flux_corrected_transport or opts.third_order_terms:
            return 2
        else:
            return 1

    @staticmethod
    def constant_1d(data, C, options: Options):
        halo = MPDATAFactory.n_halo(options)

        mpdata = MPDATA(
            step_impl=make_step(options=options, grid=data.shape, halo=halo, non_unit_g_factor=False),
            advectee=ScalarField(data, halo=halo),
            advector=VectorField((np.full(data.shape[0] + 1, C),), halo=halo)
        )
        return mpdata

    @staticmethod
    def constant_2d(data: np.ndarray, C, options: Options):
        halo = MPDATAFactory.n_halo(options)
        grid = data.shape
        GC_data = [
            np.full((grid[0] + 1, grid[1]), C[0]),
            np.full((grid[0], grid[1] + 1), C[1])
        ]
        GC = VectorField(GC_data, halo=halo)
        state = ScalarField(data=data, halo=halo)
        step = make_step(options=options, grid=grid, halo=halo, non_unit_g_factor=False)
        mpdata = MPDATA(step_impl=step, advectee=state, advector=GC)
        return mpdata

    @staticmethod
    def stream_function_2d_basic(grid, size, dt, stream_function, field, options: Options):
        halo = MPDATAFactory.n_halo(options)
        step = make_step(options=options, grid=grid, halo=halo, non_unit_g_factor=False)
        GC = nondivergent_vector_field_2d(grid, size, dt, stream_function, halo)
        advectee = ScalarField(field, halo=halo)
        return MPDATA(step, advectee=advectee, advector=GC)

    @staticmethod
    def stream_function_2d(grid, size, dt, stream_function, field_values, g_factor, options: Options):
        halo = MPDATAFactory.n_halo(options)
        step = make_step(options=options, grid=grid, halo=halo, non_unit_g_factor=True)
        GC = nondivergent_vector_field_2d(grid, size, dt, stream_function, halo)
        g_factor = ScalarField(g_factor, halo=halo)
        mpdatas = {}
        for k, v in field_values.items():
            advectee = ScalarField(np.full(grid, v), halo=halo)
            mpdatas[k] = MPDATA(step, advectee=advectee, advector=GC, g_factor=g_factor)
        return GC, EulerianFields(mpdatas)

    @staticmethod
    def advection_diffusion_1d(*,
                               options: Options,
                               advectee: np.ndarray,
                               advector: float,
                               mu_coeff: float,
                               boundary_conditions
                               ):
        assert advectee.ndim == 1
        halo = MPDATAFactory.n_halo(options)
        grid = advectee.shape
        stepper = make_step(options=options, grid=grid, halo=halo, non_unit_g_factor=False, mu_coeff=mu_coeff)
        return MPDATA(stepper,
                      advectee=ScalarField(advectee, halo=halo, boundary_conditions=(boundary_conditions, boundary_conditions)),
                      advector=VectorField((np.full(grid[0]+1, advector),), halo=halo, boundary_conditions=(boundary_conditions,boundary_conditions))
                      )

    @staticmethod
    def condensational_growth(nr, r_min, r_max, dt, grid_layout, psi_coord, pdf_of_r, drdt_of_r, opts: Options):
        # psi = psi(p)
        dp_dr = psi_coord.dx_dr
        dx_dr = grid_layout.dx_dr

        xh, dx = np.linspace(
            grid_layout.x(r_min),
            grid_layout.x(r_max),
            nr + 1,
            retstep=True
        )
        rh = grid_layout.r(xh)

        x = np.linspace(
            xh[0] + dx / 2,
            xh[-1] - dx / 2,
            nr
        )
        r = grid_layout.r(x)

        psi = discretised_analytical_solution(rh, lambda r: pdf_of_r(r) / psi_coord.dx_dr(r))

        dp_dt = drdt_of_r(rh) * dp_dr(rh)
        G = dp_dr(r) / dx_dr(r)

        # C = dr_dt * dt / dr
        # GC = dp_dr / dx_dr * dr_dt * dt / dr =
        #        \       \_____ / _..____/
        #         \_____.._____/    \_ dt/dx
        #               |
        #             dp_dt

        GCh = dp_dt * dt / dx

        # CFL condition
        np.testing.assert_array_less(np.abs(GCh), 1)

        n_halo = MPDATAFactory.n_halo(opts)
        # TODO: implementation leak: the double bc are for 2D
        g_factor = ScalarField(G, halo=n_halo, boundary_conditions=(Extrapolated, Extrapolated))
        state = ScalarField(psi, halo=n_halo, boundary_conditions=(Zero, Zero))
        GC_field = VectorField([GCh], halo=n_halo, boundary_conditions=(Zero, Zero))
        stepper = make_step(
            options=opts,
            grid=psi.shape,
            halo=n_halo,
            non_unit_g_factor=True
        )
        return (
            MPDATA(step_impl=stepper, g_factor=g_factor, advectee=state, advector=GC_field),
            r,
            rh,
            dx
        )
