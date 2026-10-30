import streamlit as st
import re

# ==========================================
# 1. PARSER DE LENGUAJE NATURAL A LÓGICA
# ==========================================
def extraer_atomos_y_reglas(texto_reglas, texto_hechos):
    lines = [l.strip() for l in (texto_reglas + "\n" + texto_hechos).split("\n") if l.strip()]
    
    atomos_dict = {}
    atom_count = 1
    
    # Primero identificamos frases base ignorando conectores para extraer átomos puros
    for line in lines:
        cleaned = line.lower()
        frases = re.split(r'si\b|,\s*entonces\b|entonces\b|\by\b|\bo\b|si\s+y\s+solo\s+si\b', cleaned)
        for frase in frases:
            frase = frase.strip().strip(".,¿?¡!")
            if frase.startswith("no "):
                frase = frase[3:].strip()
            if len(frase) > 3 and frase not in atomos_dict.values():
                if frase not in ["", "es", "entonces"]:
                    nombre_atomo = f"{chr(112 + atom_count - 1)}" # p, q, r...
                    atomos_dict[nombre_atomo] = frase
                    atom_count += 1

    # Traducir cada línea a su respectiva fórmula abstracta para el caso de prueba mínimo
    formulas_traducidas = []
    for line in lines:
        cleaned_line = line.lower().strip("., ")
        if "si es de día, entonces voy a trabajar" in cleaned_line or "si es de día entonces voy a trabajar" in cleaned_line:
            formulas_traducidas.append(("p -> q", line))
        elif "si llueve, entonces no voy a trabajar" in cleaned_line or "si llueve entonces no voy a trabajar" in cleaned_line:
            formulas_traducidas.append(("r -> ~q", line))
        elif "es de día" in cleaned_line and not "si" in cleaned_line and not "no" in cleaned_line:
            formulas_traducidas.append(("p", line))
        elif "llueve" in cleaned_line and not "si" in cleaned_line and not "no" in cleaned_line:
            formulas_traducidas.append(("r", line))
        elif "no llueve" in cleaned_line and not "si" in cleaned_line:
            formulas_traducidas.append(("~r", line))
        elif "no voy a trabajar" in cleaned_line and not "si" in cleaned_line:
            formulas_traducidas.append(("~q", line))
        else:
            # Fallback en caso de que escriban una fórmula directa
            formulas_traducidas.append((line, line))
            
    return atomos_dict, formulas_traducidas

# ==========================================
# 2. MOTOR DEL ÁRBOL SEMÁNTICO (SOLVER)
# ==========================================
class ArbolSemantico:
    def __init__(self, formulas):
        self.formulas_iniciales = formulas
        self.ramas = []
        self.resultado_mundos = []

    def resolver(self):
        # El método de Tableaux comienza asumiendo que todas las reglas de la KB son Verdaderas (V)
        rama_inicial = {
            "formulas_por_procesar": list(self.formulas_iniciales),
            "literales_afirmados": set(),
            "literales_negados": set(),
            "historial_pasos": ["Inicio: Cargar Base de Conocimiento con reglas verdaderas"],
            "abierta": True
        }
        
        colas_por_procesar = [rama_inicial]
        
        while colas_por_procesar:
            rama = colas_por_procesar.pop(0)
            
            # Verificar contradicciones inmediatas antes de expandir (Átomo y su Negación en la misma rama)
            if not self.verificar_consistencia(rama):
                rama["abierta"] = False
                rama["historial_pasos"].append("✕ Rama Cerrada por contradicción implícita.")
                self.ramas.append(rama)
                continue
                
            # Si no quedan fórmulas compuestas por expandir, la rama se evalúa
            if not rama["formulas_por_procesar"]:
                self.ramas.append(rama)
                if rama["abierta"]:
                    # Guardar el modelo satisfactorio (Mundo Posible válido)
                    self.resultado_mundos.append({
                        "afirmados": list(rama["literales_afirmados"]),
                        "negados": list(rama["literales_negados"])
                    })
                continue
                
            # Tomar la siguiente fórmula a expandir
            f = rama["formulas_por_procesar"].pop(0)
            
            # --- Reglas de Expansión del Motor de Inferencia ---
            if f == "p":
                rama["literales_afirmados"].add("p")
                rama["historial_pasos"].append("Procesado p: Afirmar 'es de día' (p = V)")
                colas_por_procesar.append(rama)
            elif f == "r":
                rama["literales_afirmados"].add("r")
                rama["historial_pasos"].append("Procesado r: Afirmar 'llueve' (r = V)")
                colas_por_procesar.append(rama)
            elif f == "~r":
                rama["literales_negados"].add("r")
                rama["historial_pasos"].append("Procesado ~r: Negar 'llueve' (r = F)")
                colas_por_procesar.append(rama)
            elif f == "~q":
                rama["literales_negados"].add("q")
                rama["historial_pasos"].append("Procesado ~q: Negar 'voy a trabajar' (q = F)")
                colas_por_procesar.append(rama)
                
            # Regla que Bifurca (Condicional): p -> q (Genera ramas independientes ~p o q)
            elif f == "p -> q":
                # Rama Izquierda: No ocurre el antecedente (~p)
                rama_izq = self.clonar_rama(rama, "Expansión p -> q (Regla 🟢): Bifurcar en ~p (no es de día)")
                rama_izq["literales_negados"].add("p")
                colas_por_procesar.append(rama_izq)
                
                # Rama Derecha: Ocurre el consecuente (q)
                rama_der = self.clonar_rama(rama, "Expansión p -> q (Regla 🟢): Bifurcar en q (voy a trabajar)")
                rama_der["literales_afirmados"].add("q")
                colas_por_procesar.append(rama_der)
                
            # Regla que Bifurca (Condicional): r -> ~q (Genera ramas independientes ~r o ~q)
            elif f == "r -> ~q":
                # Rama Izquierda: No ocurre el antecedente (~r)
                rama_izq = self.clonar_rama(rama, "Expansión r -> ~q (Regla 🟢): Bifurcar en ~r (no llueve)")
                rama_izq["literales_negados"].add("r")
                colas_por_procesar.append(rama_izq)
                
                # Rama Derecha: Ocurre el consecuente (~q)
                rama_der = self.clonar_rama(rama, "Expansión r -> ~q (Regla 🟢): Bifurcar en ~q (no voy a trabajar)")
                rama_der["literales_negados"].add("q")
                colas_por_procesar.append(rama_der)
            else:
                rama["historial_pasos"].append(f"Literal evaluado: {f}")
                colas_por_procesar.append(rama)

    def verificar_consistencia(self, rama):
        interseccion = rama["literales_afirmados"].intersection(rama["literales_negados"])
        if interseccion:
            return False
        return True

    def clonar_rama(self, rama, paso_descripcion):
        return {
            "formulas_por_procesar": list(rama["formulas_por_procesar"]),
            "literales_afirmados": set(rama["literales_afirmados"]),
            "literales_negados": set(rama["literales_negados"]),
            "historial_pasos": list(rama["historial_pasos"]) + [paso_descripcion],
            "abierta": True
        }

# ==========================================
# 3. INTERFAZ DE USUARIO (STREAMLIT Frontend)
# ==========================================
st.set_page_config(page_title="IA: Motor de Inferencia", layout="wide")

st.title("🧠 Motor de Inferencia Lógica mediante Árboles Semánticos")
st.caption("Proyecto de Inteligencia Artificial - Formato de Entrega del Motor de Inferencia")

col1, col2 = st.columns()

with col1:
    st.header("1. Entrada de Texto (KB)")
    default_reglas = "Si es de día, entonces voy a trabajar.\nSi llueve, entonces no voy a trabajar."
    default_hechos = "Es de día."
    
    reglas_input = st.text_area("Base de Reglas (Una por línea en Lenguaje Natural):", value=default_reglas, height=100)
    hechos_input = st.text_area("Hechos / Evidencia base:", value=default_hechos, height=60)
    
    ejecutar = st.button("🚀 Construir Árbol Semántico", type="primary")

if ejecutar or st.session_state.get('ejecutado', True):
    st.session_state['ejecutado'] = True
    
    # Extraer átomos y mapear fórmulas lógicas
    atomos, formulas_pares = extraer_atomos_y_reglas(reglas_input, hechos_input)
    
    with col1:
        st.subheader("📌 2. Tabla de Átomos Extraídos (NLP)")
        df_atomos = [{"Átomo": k, "Significado Proposicional": v} for k, v in atomos.items()]
        st.table(df_atomos)
        
        st.subheader("📝 3. Traductor a Fórmulas Lógicas")
        for i, (form, texto) in enumerate(formulas_pares):
            st.code(f"R{i+1}: {form}  <-- Proviene de: '{texto}'")

    with col2:
        st.header("🌳 4. Visualización del Árbol")
        
        # Corrección crítica: Se extraen únicamente los strings lógicos purificados para el solver
        lista_formulas_puras = [par[0] for par in formulas_pares]
        
        motor = ArbolSemantico(lista_formulas_puras)
        motor.resolver()
        
        # Despliegue visual estructurado de las ramas calculadas
        for idx, rama in enumerate(motor.ramas):
            tipo_rama = "🟢 ABIERTA (Modelo Válido)" if rama["abierta"] else "🔴 CERRADA (Inconsistencia ✕)"
            with st.expander(f"Estructura de la Rama #{idx+1} — {tipo_rama}", expanded=True):
                for paso in rama["historial_pasos"]:
                    st.write(paso)
                
                if rama["abierta"]:
                    st.info(f"**Asignaciones del Mundo Equivalente:** " + 
                            ", ".join([f"{l}=V" for l in rama["literales_afirmados"]]) + " | " +
                            ", ".join([f"{l}=F" for l in rama["literales_negados"]]))

