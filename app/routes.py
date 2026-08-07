from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify

from acoustic_core.models import Room, Surface, Material, BANDAS_OCTAVA
from acoustic_core.resonance import calculate_modes, detect_degenerate_modes, detect_overlapping_modes
from acoustic_core.reverberation import calculate_rt60, rt60_promedio_sabine
from acoustic_core.evaluation import (
    calculate_schroeder, calculate_modal_bandwidth,
    evaluate_bonello, find_degenerate_dimensions, get_mode_distribution,
)
from acoustic_core.design import find_closest_ratio, get_rt60_target
from acoustic_core.presets import MATERIALES_PRESETS
from .helpers import create_plot, create_rt60_plot, create_band_comparison_plot

main = Blueprint('main', __name__)

NOMBRES_SUPERFICIES = ["Frente", "Contrafrente", "Lat Izq", "Lat Der", "Piso", "Techo"]

SUPERFICIE_AREAS = [
    lambda l, a, h: a * h,
    lambda l, a, h: a * h,
    lambda l, a, h: l * h,
    lambda l, a, h: l * h,
    lambda l, a, h: l * a,
    lambda l, a, h: l * a,
]


def _build_room(form: dict) -> Room | None:
    try:
        largo = float(form.get('largo'))
        ancho = float(form.get('ancho'))
        alto = float(form.get('alto'))
        uso = form.get('uso', '').strip() or None
    except (ValueError, TypeError):
        return None

    if largo <= 0 or ancho <= 0 or alto <= 0:
        return None

    superficies = []
    for i in range(6):
        nombre = NOMBRES_SUPERFICIES[i]
        area = SUPERFICIE_AREAS[i](largo, ancho, alto)
        mat_nombre = form.get(f'material_{i + 1}', 'Concreto')

        if mat_nombre in MATERIALES_PRESETS:
            base = MATERIALES_PRESETS[mat_nombre]
        else:
            base = Material(nombre=mat_nombre, alpha_unico=0.1)

        alphas_personalizados = {}
        for banda in BANDAS_OCTAVA:
            key = f'alfa_{banda}_{i + 1}'
            val = form.get(key)
            if val is not None and val.strip() != '':
                try:
                    a = float(val)
                    if 0 <= a <= 1:
                        alphas_personalizados[banda] = a
                except ValueError:
                    pass

        if alphas_personalizados:
            material = Material(nombre=mat_nombre, alphas=alphas_personalizados)
        else:
            material = base

        superficies.append(Surface(nombre=nombre, area=area, material=material))

    try:
        return Room(largo=largo, ancho=ancho, alto=alto, superficies=superficies, uso=uso)
    except Exception:
        return None


def _build_room_from_json(data: dict) -> Room | None:
    try:
        largo = float(data['largo'])
        ancho = float(data['ancho'])
        alto = float(data['alto'])
        uso = data.get('uso', '').strip() or None
    except (ValueError, TypeError, KeyError):
        return None

    if largo <= 0 or ancho <= 0 or alto <= 0:
        return None

    superficies = []
    for i in range(6):
        nombre = NOMBRES_SUPERFICIES[i]
        area = SUPERFICIE_AREAS[i](largo, ancho, alto)

        sup_data = data.get('superficies', [{}] * 6)
        if i < len(sup_data) and isinstance(sup_data[i], dict):
            sd = sup_data[i]
            mat_nombre = sd.get('material', 'Concreto')
            custom_alphas = sd.get('alphas', {})
        else:
            mat_nombre = 'Concreto'
            custom_alphas = {}

        if mat_nombre in MATERIALES_PRESETS:
            base = MATERIALES_PRESETS[mat_nombre]
        else:
            base = Material(nombre=mat_nombre, alpha_unico=0.1)

        if custom_alphas:
            material = Material(nombre=mat_nombre, alphas=custom_alphas)
        else:
            material = base

        superficies.append(Surface(nombre=nombre, area=area, material=material))

    try:
        return Room(largo=largo, ancho=ancho, alto=alto, superficies=superficies, uso=uso)
    except Exception:
        return None


def _compute_all(room: Room) -> dict:
    modos = calculate_modes(room)
    rt60_bandas = calculate_rt60(room)
    rt60_prom = rt60_promedio_sabine(room)
    delta_f = calculate_modal_bandwidth(rt60_prom)
    modos = detect_degenerate_modes(modos)
    modos = detect_overlapping_modes(modos, delta_f)
    frecuencias = [m.frecuencia for m in modos]
    bonello = evaluate_bonello(frecuencias)
    f_schroeder = calculate_schroeder(rt60_prom, room.volumen)
    distribucion = get_mode_distribution(modos)
    proporciones = find_closest_ratio(room.largo, room.ancho, room.alto)
    degeneracion_dims = find_degenerate_dimensions(room.largo, room.ancho, room.alto)
    objetivo = get_rt60_target(room.uso) if room.uso else None
    if objetivo:
        for banda in BANDAS_OCTAVA:
            sabine = rt60_bandas[banda]["Sabine"]
            target = objetivo["valores"].get(banda, 0)
            objetivo["diferencias"] = objetivo.get("diferencias", {})
            objetivo["diferencias"][banda] = round(abs(sabine - target), 2)

    return {
        "modos": [m.model_dump(mode='json') for m in modos],
        "frecuencias": frecuencias,
        "cantidad_modos": len(modos),
        "distribucion": distribucion,
        "rt60_bandas": rt60_bandas,
        "rt60_promedio": rt60_prom,
        "f_schroeder": f_schroeder,
        "delta_f": delta_f,
        "bonello": bonello,
        "proporciones": proporciones,
        "degeneracion_dimensiones": degeneracion_dims,
        "objetivo": objetivo,
    }


@main.route('/')
def index():
    return render_template('index.html', materials=MATERIALES_PRESETS, bandas=BANDAS_OCTAVA)


@main.route('/results', methods=['POST'])
def results():
    room = _build_room(request.form)
    if room is None:
        flash('Ingrese valores numéricos válidos (dimensiones > 0, α entre 0 y 1).')
        return redirect(url_for('main.index'))

    datos = _compute_all(room)

    plot_url = create_plot(list(datos['bonello']['bandas'].keys()),
                           list(datos['bonello']['bandas'].values()))
    rt60_plot_url = create_rt60_plot(datos['rt60_bandas'])
    comparacion_url = None
    if datos['objetivo']:
        comparacion_url = create_band_comparison_plot(datos['rt60_bandas'], datos['objetivo']['valores'])

    return render_template('results.html',
                           datos=datos,
                           plot_url=plot_url,
                           rt60_plot_url=rt60_plot_url,
                           comparacion_url=comparacion_url,
                           bandas=BANDAS_OCTAVA,
                           metodos_rt60=["Sabine", "Eyring", "Millington", "FitzRoy"])


@main.route('/api/v1/calculate', methods=['POST'])
def api_calculate():
    data = request.get_json(force=True)
    if not data:
        return jsonify({'error': 'Se requiere cuerpo JSON'}), 400

    room = _build_room_from_json(data)
    if room is None:
        return jsonify({'error': 'Datos inválidos: dimensiones > 0, superficies con materiales válidos'}), 400

    datos = _compute_all(room)
    return jsonify(datos)
