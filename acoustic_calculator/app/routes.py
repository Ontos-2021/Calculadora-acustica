from flask import Blueprint, render_template, request, redirect, url_for
from .utils.calculations import calculate_resonance_modes, calculate_rt60
from .utils.evaluations import criterio_de_bonello

main = Blueprint('main', __name__)

@main.route('/')
def index():
    return render_template('index.html')

@main.route('/results', methods=['POST'])
def results():
    largo = float(request.form.get('largo'))
    ancho = float(request.form.get('ancho'))
    alto = float(request.form.get('alto'))
    alfas = [float(request.form.get(f'alfa_{i}')) for i in range(1, 7)]

    modos_resonancia = calculate_resonance_modes(largo, ancho, alto)
    rt60_values = calculate_rt60(largo, ancho, alto, alfas)
    bonello_result = criterio_de_bonello(modos_resonancia['frequencies'])

    return render_template('results.html', modos_resonancia=modos_resonancia, rt60_values=rt60_values, bonello_result=bonello_result)
