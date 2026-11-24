# ALUC (halluref-AI) — Agente de IA para Auditoria e Detecção de Alucinações Bibliográficas

Sistema de auditoria automatizada de referências bibliográficas em documentos acadêmicos (`.pdf`, `.bib`, `.tex`) projetado para detectar **referências alucinadas** geradas por Modelos de Linguagem (LLMs).

## Funcionalidades Principais

- **OCR local no Windows:** PDFs digitalizados podem ser lidos pelo reconhecimento de texto do Windows usando um idioma de OCR instalado no perfil.
- **Extração local:** Identifica a bibliografia em PDF e LaTeX e interpreta BibTeX diretamente. Se necessário, usa uma chamada opcional ao Gemini para estruturar um bloco bibliográfico identificado.
- **Auditoria em Python:** Resolve DOIs e consulta Crossref, OpenAlex e Semantic Scholar em cascata. A matriz de decisão classifica cada referência a partir dos metadados encontrados.
- **Investigação em lote:** Usa até duas chamadas opcionais ao Gemini para planejar buscas e avaliar candidatos. O Python verifica as correções sugeridas e registra a fonte e o BibTeX no relatório.
- **Progresso:** A interface web e a CLI exibem a etapa atual, incluindo a espera por serviços externos. O relatório registra as chamadas ao Gemini por etapa, com limite de três por documento.
- **Detecção da Taxonomia Completa de Alucinações (RN01–RN05):**
  - *Invenção Total (Ghost Reference)*
  - *Referência Quimera (Mosaico de Metadados / Atribuição Falsa de Autoria)*
  - *Sequestro ou Invenção de DOI (DOI 404 ou DOI Cruzado/Hijacked)*
  - *Distorção de Veículo ou Ano (tolerância de $\le 2$ anos)*
  - *Literatura Cinzenta, Livros Locais, Normas Técnicas e URLs (Revisão Manual — RN05)*
- **Exportação Multi-Formato (RF06):** Relatórios detalhados em **Markdown (`.md`)**, **JSON (`.json`)** e **PDF (`.pdf`)**.

## Como Executar

### 1. Configurar ambiente virtual
```powershell
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
```

### 2. Configurar variáveis de ambiente
Para ativar a assistência do Gemini, copie `.env.example` para `.env` e informe sua `GEMINI_API_KEY` (Google AI Studio). A auditoria em Python também funciona sem essa configuração.
```powershell
Copy-Item .env.example .env
```

### 3. Executar Interface Web (Streamlit)
```powershell
.\.venv\Scripts\streamlit run app.py
```

### 4. Executar via Linha de Comando (CLI)
```powershell
.\.venv\Scripts\python cli.py audit tests/fixtures/sample_references.bib --output-dir ./reports --format all
```

### 5. Executar Testes Automatizados
```powershell
.\.venv\Scripts\pytest tests/ -v
```
