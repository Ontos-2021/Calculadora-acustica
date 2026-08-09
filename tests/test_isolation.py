import math

import pytest

from acoustic_core.isolation import (
    BANDAS_TERCIO_OCTAVA,
    ISO717_BANDS_HZ,
    ISO717_REFERENCE_VALUES,
    ISO717_SPECTRUM_C,
    ISO717_SPECTRUM_CTR,
    NC_CURVES,
    NC_FREQS,
    NR_CURVES,
    NR_FREQS,
    OCTAVE_BANDS_HZ,
    RW_REFERENCE_OFFSETS,
    STC_BANDS_HZ,
    STC_REFERENCE_OFFSETS,
    aggregate_flanking_paths,
    calculate_rw,
    calculate_stc,
    compare_isolation_target,
    compare_nc_target,
    compare_nr_target,
    compare_target_by_use,
    coincidence_notch,
    critical_frequency,
    double_panel_tl,
    double_panel_tl_details,
    energetic_flanking_sum,
    evaluate_nc,
    evaluate_nr,
    get_nc_target,
    get_nr_target,
    mass_law_tl,
    msr_resonance,
    plate_critical_frequency,
    rectangular_lined_duct_attenuation,
    single_panel_tl,
    single_panel_tl_details,
)


def _stc_curve_for_rating(rating, uniform_deficiency=2):
    return {
        str(frequency): rating + STC_REFERENCE_OFFSETS[frequency] - uniform_deficiency
        for frequency in STC_BANDS_HZ
    }


def _rw_curve_for_rating(rating, uniform_deficiency=2):
    return {
        str(frequency): rating + RW_REFERENCE_OFFSETS[frequency] - uniform_deficiency
        for frequency in ISO717_BANDS_HZ
    }


def _tabulated_curve(frequencies, values):
    return {str(frequency): value for frequency, value in zip(frequencies, values)}


class TestBandConstants:
    def test_standard_third_octave_sets(self):
        assert len(STC_BANDS_HZ) == 16
        assert STC_BANDS_HZ[0] == 125
        assert STC_BANDS_HZ[-1] == 4000
        assert len(ISO717_BANDS_HZ) == 16
        assert ISO717_BANDS_HZ[0] == 100
        assert ISO717_BANDS_HZ[-1] == 3150
        assert BANDAS_TERCIO_OCTAVA[0] == "100"
        assert BANDAS_TERCIO_OCTAVA[-1] == "4000"

    def test_iso_reference_and_spectra_are_complete(self):
        assert ISO717_REFERENCE_VALUES[500] == 52
        assert set(ISO717_REFERENCE_VALUES) == set(ISO717_BANDS_HZ)
        assert set(ISO717_SPECTRUM_C) == set(ISO717_BANDS_HZ)
        assert set(ISO717_SPECTRUM_CTR) == set(ISO717_BANDS_HZ)
        assert ISO717_SPECTRUM_CTR[100] > ISO717_SPECTRUM_C[100]


class TestMassLaw:
    def test_basic(self):
        tl = mass_law_tl(50, 500)
        assert 20 < tl < 60

    @pytest.mark.parametrize(
        ("first", "second"),
        [
            (mass_law_tl(10, 500), mass_law_tl(20, 500)),
            (mass_law_tl(50, 500), mass_law_tl(50, 1000)),
        ],
    )
    def test_doubling_mass_or_frequency_adds_six_db(self, first, second):
        assert second - first == pytest.approx(6.0, abs=0.1)

    @pytest.mark.parametrize(
        ("mass", "frequency"),
        [(0, 500), (-1, 500), (10, 0), (10, math.nan), (math.inf, 500)],
    )
    def test_invalid_inputs_raise(self, mass, frequency):
        with pytest.raises(ValueError):
            mass_law_tl(mass, frequency)


class TestCriticalFrequency:
    def test_legacy_thicker_panel_has_lower_fc(self):
        assert critical_frequency(0.1) < critical_frequency(0.05)

    def test_thin_plate_formula_matches_independent_expression(self):
        thickness = 0.0125
        density = 800.0
        young_modulus = 2.5e9
        poisson = 0.3
        bending_stiffness = young_modulus * thickness**3 / (12 * (1 - poisson**2))
        expected = 343**2 / (2 * math.pi) * math.sqrt(
            density * thickness / bending_stiffness
        )
        result = plate_critical_frequency(
            thickness, density, young_modulus, poisson
        )
        assert result == pytest.approx(expected, abs=0.1)

    def test_critical_frequency_property_api(self):
        direct = plate_critical_frequency(0.01, 2500, 70e9, 0.23)
        compatible = critical_frequency(
            0.01,
            density_kgm3=2500,
            young_modulus_pa=70e9,
            poisson_ratio=0.23,
        )
        assert compatible == direct

    def test_partial_or_invalid_properties_raise(self):
        with pytest.raises(ValueError, match="supplied together"):
            critical_frequency(0.01, density_kgm3=2500)
        with pytest.raises(ValueError, match="poisson_ratio"):
            plate_critical_frequency(0.01, 2500, 70e9, 0.5)


class TestSinglePanel:
    def test_legacy_api_returns_six_octave_bands(self):
        tl = single_panel_tl(50, 0.1)
        assert tuple(map(int, tl)) == OCTAVE_BANDS_HZ

    def test_can_return_standard_third_octave_grid(self):
        tl = single_panel_tl(50, 0.1, frequencies_hz=STC_BANDS_HZ)
        assert tuple(map(int, tl)) == STC_BANDS_HZ
        assert all(math.isfinite(value) and value >= 0 for value in tl.values())

    def test_coincidence_notch_is_localized(self):
        assert coincidence_notch(3000, 3000) == pytest.approx(10.0)
        assert coincidence_notch(100, 3000) < coincidence_notch(3000, 3000)

    def test_physical_properties_move_coincidence(self):
        flexible = single_panel_tl_details(
            10,
            0.0125,
            density_kgm3=800,
            young_modulus_pa=2.5e9,
            poisson_ratio=0.3,
            loss_factor=0.03,
            frequencies_hz=[1000, 2500, 4000],
        )
        stiff = single_panel_tl_details(
            10,
            0.0125,
            density_kgm3=800,
            young_modulus_pa=10e9,
            poisson_ratio=0.3,
            loss_factor=0.03,
            frequencies_hz=[1000, 2500, 4000],
        )
        assert stiff["critical_frequency_hz"] < flexible["critical_frequency_hz"]
        assert flexible["is_estimate"] is True
        assert "not a laboratory" in flexible["assumptions"][0]

    def test_higher_loss_factor_reduces_dip(self):
        low_loss = single_panel_tl_details(
            10,
            0.0125,
            "yeso",
            loss_factor=0.01,
            frequencies_hz=[2800],
        )
        high_loss = single_panel_tl_details(
            10,
            0.0125,
            "yeso",
            loss_factor=0.10,
            frequencies_hz=[2800],
        )
        assert high_loss["tl"]["2800"] > low_loss["tl"]["2800"]
        assert high_loss["coincidence_depth_db"] < low_loss["coincidence_depth_db"]

    def test_far_from_coincidence_reaches_mass_law_asymptote(self):
        details = single_panel_tl_details(
            20, 0.1, "concreto", frequencies_hz=[4000]
        )
        assert details["tl"]["4000"] == pytest.approx(
            details["mass_law_asymptote_db"]["4000"], abs=0.2
        )


class TestDoublePanel:
    def test_legacy_api_returns_six_octave_bands(self):
        assert len(double_panel_tl(50, 50, 0.05)) == 6

    def test_mass_air_mass_resonance_matches_physics(self):
        expected = 343 / (2 * math.pi) * math.sqrt(
            1.21 * (50 + 20) / (50 * 20 * 0.1)
        )
        assert msr_resonance(50, 20, 0.1) == pytest.approx(expected, abs=0.1)

    def test_larger_gap_lowers_resonance(self):
        assert msr_resonance(20, 20, 0.2) < msr_resonance(20, 20, 0.05)

    def test_below_resonance_approaches_combined_mass(self):
        f0 = msr_resonance(12, 18, 0.09)
        frequency = f0 / 4
        details = double_panel_tl_details(
            12, 18, 0.09, False, frequencies_hz=[frequency]
        )
        key = next(iter(details["tl"]))
        assert details["regime_by_band"][key] == "below_resonance_combined_mass"
        assert details["tl"][key] == pytest.approx(
            details["combined_mass_asymptote_db"][key], abs=0.2
        )

    def test_resonance_produces_a_transmission_loss_dip(self):
        f0 = msr_resonance(12, 18, 0.09)
        details = double_panel_tl_details(
            12, 18, 0.09, False, frequencies_hz=[f0 / 2, f0, f0 * 2]
        )
        values = list(details["tl"].values())
        assert values[1] < values[0]
        assert values[1] < values[2]
        assert max(details["resonance_penalty_db"].values()) == pytest.approx(12, abs=0.1)

    def test_cavity_absorption_is_monotonic(self):
        empty = double_panel_tl(
            15, 20, 0.1, False, cavity_absorption=0, frequencies_hz=STC_BANDS_HZ
        )
        filled = double_panel_tl(
            15, 20, 0.1, False, cavity_absorption=0.8, frequencies_hz=STC_BANDS_HZ
        )
        assert all(filled[band] >= empty[band] for band in empty)
        assert any(filled[band] > empty[band] for band in empty)

    def test_explicit_bridge_penalty_is_monotonic(self):
        unbridged = double_panel_tl(
            20, 20, 0.1, False, bridge_penalty_db=0, frequencies_hz=[1000]
        )
        bridged = double_panel_tl(
            20, 20, 0.1, False, bridge_penalty_db=7, frequencies_hz=[1000]
        )
        assert unbridged["1000"] - bridged["1000"] == pytest.approx(7.0)

    def test_both_leaf_masses_affect_high_frequency_result(self):
        light_second = double_panel_tl(
            20, 10, 0.1, False, frequencies_hz=[2000]
        )
        heavy_second = double_panel_tl(
            20, 40, 0.1, False, frequencies_hz=[2000]
        )
        assert heavy_second["2000"] > light_second["2000"]

    @pytest.mark.parametrize(
        ("args", "kwargs"),
        [((0, 20, 0.1), {}), ((20, 20, -0.1), {}), ((20, 20, 0.1), {"cavity_absorption": 1.1})],
    )
    def test_invalid_inputs_raise(self, args, kwargs):
        with pytest.raises(ValueError):
            double_panel_tl(*args, **kwargs)


class TestSTC:
    def test_exact_shifted_contour_at_total_deficiency_limit(self):
        result = calculate_stc(_stc_curve_for_rating(50))
        assert result["stc"] == 50
        assert result["total_deficiency_db"] == 32
        assert result["max_deficiency_db"] == 2
        assert result["contour_db"]["500"] == 50
        assert result["input_complete"] is True
        assert result["is_estimate"] is False
        assert result["not_certification"] is True

    def test_single_band_eight_db_limit_is_inclusive(self):
        rating = 47
        curve = {
            str(frequency): rating + STC_REFERENCE_OFFSETS[frequency] + 20
            for frequency in STC_BANDS_HZ
        }
        curve["125"] = rating + STC_REFERENCE_OFFSETS[125] - 8
        result = calculate_stc(curve)
        assert result["stc"] == rating
        assert result["max_deficiency_db"] == 8
        assert result["total_deficiency_db"] == 8

    def test_total_32_db_limit_is_inclusive_and_next_shift_fails(self):
        rating = 52
        curve = {
            str(frequency): rating + STC_REFERENCE_OFFSETS[frequency] + 20
            for frequency in STC_BANDS_HZ
        }
        for frequency in STC_BANDS_HZ[:4]:
            curve[str(frequency)] = rating + STC_REFERENCE_OFFSETS[frequency] - 8
        result = calculate_stc(curve)
        assert result["stc"] == rating
        assert result["total_deficiency_db"] == 32

    def test_nrc_public_lab_curve_reproduces_published_stc_33(self):
        # NRC Canada IRC-IR-761 specimen TL-93-166, tested to E90/E413.
        curve = {
            "125": 9, "160": 16, "200": 31, "250": 34,
            "315": 36, "400": 43, "500": 44, "630": 44,
            "800": 49, "1000": 51, "1250": 53, "1600": 54,
            "2000": 53, "2500": 45, "3150": 40, "4000": 43,
        }
        result = calculate_stc(curve)
        assert result["stc"] == 33
        assert result["max_deficiency_db"] == 8

    def test_half_db_input_is_rounded_half_up_before_fit(self):
        curve = _stc_curve_for_rating(40)
        curve["125"] = 30.5
        result = calculate_stc(curve)
        assert result["tl_used_db"]["125"] == 31

    def test_legacy_octaves_are_retained_but_labelled_estimate(self):
        legacy = {
            "125": 30, "250": 35, "500": 40,
            "1000": 45, "2000": 50, "4000": 55,
        }
        result = calculate_stc(legacy)
        assert isinstance(result["stc"], int)
        assert result["input_complete"] is False
        assert result["is_estimate"] is True
        assert "interpolation" in result["input_basis"]

    @pytest.mark.parametrize(
        "curve",
        [
            {},
            {"125": 30, "160": 32},
            {**_stc_curve_for_rating(40), "500": math.nan},
            {**_stc_curve_for_rating(40), 125: 30},
        ],
    )
    def test_invalid_data_raise(self, curve):
        with pytest.raises(ValueError):
            calculate_stc(curve)


class TestRw:
    def test_exact_shifted_contour_at_total_deficiency_limit(self):
        result = calculate_rw(_rw_curve_for_rating(50))
        assert result["rw"] == 50
        assert result["total_deficiency_db"] == 32
        assert result["contour_db"]["500"] == 50
        assert result["c"] == -2
        assert result["ctr"] == -6
        assert result["rw_c"] == 48
        assert result["rw_ctr"] == 44

    def test_iso_allows_large_single_band_deficiency(self):
        rating = 50
        curve = {
            str(frequency): rating + RW_REFERENCE_OFFSETS[frequency] + 30
            for frequency in ISO717_BANDS_HZ
        }
        curve["100"] = rating + RW_REFERENCE_OFFSETS[100] - 20
        result = calculate_rw(curve)
        assert result["max_deficiency_db"] > 8
        assert result["total_deficiency_db"] <= 32

    def test_reference_curve_shape_is_iso_not_old_three_db_slope(self):
        result = calculate_rw(_rw_curve_for_rating(45))
        contour = result["contour_db"]
        assert contour["100"] == 26
        assert contour["500"] == 45
        assert contour["1250"] == 49
        assert contour["3150"] == 49

    def test_adaptation_terms_are_energetic_not_arithmetic(self):
        result = calculate_rw(_rw_curve_for_rating(50))
        values = result["tl_used_db"]
        independent_c_level = -10 * math.log10(sum(
            10 ** ((ISO717_SPECTRUM_C[frequency] - values[str(frequency)]) / 10)
            for frequency in ISO717_BANDS_HZ
        ))
        assert result["spectrum_adapted_level_c_db"] == pytest.approx(
            independent_c_level, abs=0.1
        )

    def test_legacy_octaves_are_retained_but_labelled_estimate(self):
        legacy = {
            "125": 30, "250": 35, "500": 40,
            "1000": 45, "2000": 50, "4000": 55,
        }
        result = calculate_rw(legacy)
        assert result["is_estimate"] is True
        assert result["input_complete"] is False

    def test_partial_or_non_finite_data_raise(self):
        with pytest.raises(ValueError, match="missing required bands"):
            calculate_rw({"100": 20, "125": 22})
        with pytest.raises(ValueError, match="finite"):
            calculate_rw({**_rw_curve_for_rating(50), "1000": math.inf})


class TestNC:
    def test_public_nc_table_values(self):
        assert NC_FREQS == (63, 125, 250, 500, 1000, 2000, 4000, 8000)
        assert NC_CURVES[15] == [47, 36, 29, 22, 17, 14, 12, 11]
        assert NC_CURVES[70] == [83, 79, 75, 72, 71, 70, 69, 68]

    def test_exact_curve_boundary_selects_that_curve(self):
        result = evaluate_nc(_tabulated_curve(NC_FREQS, NC_CURVES[30]))
        assert result["nc"] == 30
        assert result["classification"] == "NC-30"
        assert all(margin == 0 for margin in result["margin_by_band_db"].values())
        assert result["input_complete"] is True

    def test_one_band_above_boundary_selects_next_curve(self):
        curve = _tabulated_curve(NC_FREQS, NC_CURVES[30])
        curve["1000"] += 0.1
        result = evaluate_nc(curve)
        assert result["nc"] == 35
        assert result["nc_by_band"]["1000"] == 35

    def test_all_bands_are_used_including_63_and_8000(self):
        curve = _tabulated_curve(NC_FREQS, NC_CURVES[20])
        curve["8000"] = NC_CURVES[45][-1]
        result = evaluate_nc(curve)
        assert result["nc"] == 45
        assert "8000" in result["governing_bands_hz"]

    def test_above_highest_curve_is_explicit(self):
        curve = _tabulated_curve(NC_FREQS, NC_CURVES[70])
        curve["63"] += 1
        result = evaluate_nc(curve)
        assert result["nc"] is None
        assert result["classification"] == ">NC-70"
        assert result["above_tabulated_range"] is True

    def test_legacy_six_bands_are_estimated_not_silently_zero_filled(self):
        legacy = {
            "125": 50, "250": 45, "500": 40,
            "1000": 35, "2000": 30, "4000": 25,
        }
        result = evaluate_nc(legacy)
        assert isinstance(result["nc"], int)
        assert result["is_estimate"] is True
        assert set(result["nc_by_band"]) == {str(frequency) for frequency in NC_FREQS}

    def test_partial_curve_raises(self):
        with pytest.raises(ValueError, match="missing required bands"):
            evaluate_nc({"125": 40, "250": 35})


class TestNR:
    def test_public_nr_table_values(self):
        assert NR_FREQS[0] == 31.5
        assert NR_CURVES[0] == [55, 36, 22, 12, 5, 0, -4, -6, -8]
        assert NR_CURVES[130][-1] == 126

    def test_exact_curve_boundary_selects_that_curve(self):
        result = evaluate_nr(_tabulated_curve(NR_FREQS, NR_CURVES[30]))
        assert result["nr"] == 30
        assert result["classification"] == "NR-30"
        assert result["input_complete"] is True

    def test_one_band_above_boundary_selects_next_curve(self):
        curve = _tabulated_curve(NR_FREQS, NR_CURVES[30])
        curve["31.5"] += 0.1
        assert evaluate_nr(curve)["nr"] == 40

    def test_accepts_62_5_nominal_key_for_63_hz_band(self):
        curve = _tabulated_curve(NR_FREQS, NR_CURVES[20])
        curve["62.5"] = curve.pop("63")
        assert evaluate_nr(curve)["nr"] == 20

    def test_above_highest_curve_is_explicit(self):
        curve = _tabulated_curve(NR_FREQS, NR_CURVES[130])
        curve["8000"] += 1
        result = evaluate_nr(curve)
        assert result["nr"] is None
        assert result["classification"] == ">NR-130"


class TestTargets:
    def test_legacy_nc_target_lookup(self):
        target = get_nc_target("estudio_grabacion")
        assert target is not None
        assert target["nc"] == 15
        assert "not certification" in target["basis"]
        assert get_nc_target("no_existe") is None

    def test_nr_target_lookup(self):
        target = get_nr_target("teatro")
        assert target["nr_max"] == 30
        assert get_nr_target("no_existe") is None

    def test_nc_and_nr_comparison_direction(self):
        assert compare_nc_target("aula", 30)["meets_all_targets"] is True
        assert compare_nc_target("aula", 35)["meets_all_targets"] is False
        assert compare_nr_target("aula", 35)["meets_all_targets"] is True

    def test_isolation_comparison_direction_and_estimate_label(self):
        result = compare_isolation_target("aula", stc=51, rw=49)
        assert result["comparisons"]["stc"]["meets_target"] is True
        assert result["comparisons"]["rw"]["meets_target"] is False
        assert result["meets_all_targets"] is False
        assert "planning estimates" in result["basis"]
        assert result["not_certification"] is True

    def test_generic_comparison_rejects_unknown_or_empty(self):
        with pytest.raises(ValueError, match="unknown use"):
            compare_target_by_use("no_existe", nc=20)
        with pytest.raises(ValueError, match="at least one"):
            compare_target_by_use("aula")


class TestLinedDuct:
    ABSORPTION = {
        "125": 0.15,
        "250": 0.35,
        "500": 0.65,
        "1000": 0.85,
        "2000": 0.80,
        "4000": 0.60,
    }

    def test_frequency_dependent_sabine_result_and_labels(self):
        result = rectangular_lined_duct_attenuation(
            0.4, 0.25, 1.0, self.ABSORPTION
        )
        assert result["insertion_loss_db"]["1000"] > result["insertion_loss_db"]["125"]
        assert result["is_estimate"] is True
        assert "Sabine" in result["method"]
        assert result["not_certification"] is True

    def test_length_is_linear_and_monotonic(self):
        short = rectangular_lined_duct_attenuation(
            0.4, 0.25, 0.5, 0.7
        )["insertion_loss_db"]
        long = rectangular_lined_duct_attenuation(
            0.4, 0.25, 1.0, 0.7
        )["insertion_loss_db"]
        assert all(long[band] == pytest.approx(2 * short[band], abs=0.11) for band in short)

    def test_more_absorptive_lining_never_reduces_attenuation(self):
        low = rectangular_lined_duct_attenuation(
            0.4, 0.25, 1.0, 0.2
        )["insertion_loss_db"]
        high = rectangular_lined_duct_attenuation(
            0.4, 0.25, 1.0, 0.8
        )["insertion_loss_db"]
        assert all(high[band] > low[band] for band in low)

    def test_lined_perimeter_fraction_is_monotonic(self):
        half = rectangular_lined_duct_attenuation(
            0.4, 0.25, 1.0, 0.7, lined_perimeter_fraction=0.5
        )["insertion_loss_db"]
        full = rectangular_lined_duct_attenuation(
            0.4, 0.25, 1.0, 0.7, lined_perimeter_fraction=1.0
        )["insertion_loss_db"]
        assert all(full[band] == pytest.approx(2 * half[band], abs=0.11) for band in half)

    @pytest.mark.parametrize(
        ("args", "kwargs"),
        [
            ((0, 0.25, 1, 0.5), {}),
            ((0.4, 0.25, 1, 1.1), {}),
            ((0.4, 0.25, 1, {"125": 0.5}), {}),
            ((0.4, 0.25, 1, 0.5), {"lined_perimeter_fraction": -0.1}),
        ],
    )
    def test_invalid_inputs_raise(self, args, kwargs):
        with pytest.raises(ValueError):
            rectangular_lined_duct_attenuation(*args, **kwargs)


class TestFlankingAggregation:
    def test_two_equal_paths_reduce_tl_by_three_db(self):
        assert energetic_flanking_sum([50, 50]) == pytest.approx(46.99, abs=0.01)

    def test_dominant_weak_path_controls_result(self):
        result = energetic_flanking_sum([60, 40, 70])
        assert result < 40
        assert result > 39.5

    def test_scalar_helper_is_explicit_estimate(self):
        result = aggregate_flanking_paths(50, [50, 60])
        assert result["apparent_tl_db"] == pytest.approx(
            energetic_flanking_sum([50, 50, 60]), abs=0.01
        )
        assert result["path_count"] == 3
        assert result["is_estimate"] is True
        assert result["not_iso_12354_prediction"] is True

    def test_curve_aggregation_is_bandwise(self):
        result = aggregate_flanking_paths(
            {"125": 40, "250": 50},
            [{"125": 40, "250": 60}],
        )
        assert result["apparent_tl_db"]["125"] == pytest.approx(36.99)
        assert result["apparent_tl_db"]["250"] == pytest.approx(49.59)

    def test_invalid_paths_raise(self):
        with pytest.raises(ValueError, match="at least one"):
            energetic_flanking_sum([])
        with pytest.raises(ValueError, match="identical"):
            aggregate_flanking_paths(
                {"125": 40, "250": 50},
                [{"125": 45}],
            )


class TestIsolationAPI:
    def test_single_panel(self, client, paid_headers):
        response = client.post("/api/v1/design/isolation/single-panel", json={
            "mass_per_area_kgm2": 50,
            "thickness_m": 0.1,
            "material_type": "concreto",
        }, headers=paid_headers)
        assert response.status_code == 200
        data = response.json()
        assert "tl" in data
        assert "fc_hz" in data
        assert "stc" in data
        assert "rw" in data

    def test_double_panel(self, client, paid_headers):
        response = client.post("/api/v1/design/isolation/double-panel", json={
            "m1_kgm2": 50,
            "m2_kgm2": 20,
            "gap_m": 0.1,
        }, headers=paid_headers)
        assert response.status_code == 200
        data = response.json()
        assert "tl" in data
        assert "f0_hz" in data

    def test_nc_legacy_request_remains_available(self, client, paid_headers):
        response = client.post("/api/v1/design/isolation/nc", json={
            "spl": {
                "125": 50, "250": 45, "500": 40,
                "1000": 35, "2000": 30, "4000": 25,
            },
        }, headers=paid_headers)
        assert response.status_code == 200
        data = response.json()
        assert "nc" in data
        assert data["is_estimate"] is True

    def test_nc_targets(self, client, paid_headers):
        response = client.get("/api/v1/design/isolation/nc-targets", headers=paid_headers)
        assert response.status_code == 200
        assert "estudio_grabacion" in response.json()
