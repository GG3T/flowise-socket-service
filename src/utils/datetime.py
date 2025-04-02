import datetime
import pytz

def get_brasilia_datetime():
    """
    Retorna a data e hora atual no fuso horário de Brasília (GMT-3).
    
    Returns:
        str: Data e hora formatada como yyyy-MM-dd HH:mm
    """
    # Define o fuso horário de Brasília
    brasilia_tz = pytz.timezone('America/Sao_Paulo')
    
    # Obtém a data e hora atual nesse fuso horário
    now = datetime.datetime.now(brasilia_tz)
    
    # Formata a data e hora como yyyy-MM-dd HH:mm
    formatted_datetime = now.strftime("%Y-%m-%d %H:%M")
    
    return formatted_datetime
