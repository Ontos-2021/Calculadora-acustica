from flask import Blueprint, render_template, request, jsonify
from .utils.data import materials
from .utils.calculations import calculate_alpha_average, calculate_rt60, calculate_resonance_modes
from .utils.helpers import create_plot

main = Blueprint('main', __name__)

@main.route('/')
def index():
    return render_template('index.html', materials=materials)

@main.route('/calculate', methods=['POST'])
def calculate():
    data = request.json
    largo = float(data['largo'])
    ancho = float(data['ancho'])
    alto = float(data['alto'])

    alfas = []
    for pared in data['paredes']:
        alpha_avg = calculate_alpha_average(materials, pared['materiales'])
        alfas.append(alpha_avg)

    rt60_values = calculate_rt60(largo, ancho, alto, alfas)
    modos_resonancia = calculate_resonance_modes(largo, ancho, alto)

    superficie_total = 2 * (largo * ancho + largo * alto + ancho * alto)
    volumen = largo * ancho * alto

    frecuencias = [modo['frecuencia'] for modo in modos_resonancia['modos']]
    counts = [frecuencias.count(freq) for freq in set(frecuencias)]
    plot_url = create_plot(list(set(frecuencias)), counts)

    resultados = {
        'superficie_total': superficie_total,
        'volumen': volumen,
        'alfas': alfas,
        'rt60': rt60_values,
        'modos_resonancia': modos_resonancia,
        'plot_url': plot_url
    }

    return jsonify(resultados)
