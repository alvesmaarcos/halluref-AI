# ALUC (halluref-AI) — Agente de IA para Auditoria e Detecção de Alucinações Bibliográficas

Sistema de auditoria automatizada de referências bibliográficas em documentos acadêmicos (`.pdf`, `.bib`, `.tex`) projetado para detectar **referências alucinadas** geradas por Modelos de Linguagem (LLMs).

## Funcionalidades Principais

- **Isolamento com Privacidade de Manuscrito (RF01, RF02, RNF02):** Extrai apenas a seção final de referências de arquivos PDF e LaTeX (`.tex`), além de arquivos BibTeX (`.bib`), garantindo que o texto principal do artigo não seja enviado a APIs de terceiros.
- **Parser Semântico via Gemini Flash (RF03, RNF03):** Estrutura referências brutas em JSON padronizado usando `gemini-3.8-flash` (SDK `google-genai`) com configuração determinística (`seed=0`).
- **Agente Auditor com Tool-Calling em Cascata (RF04):** Orquestra consultas encadeadas em bases científicas abertas e gratuitas:
  1. Resolução direta de DOI (**Crossref / doi.org** — **RN01**)
  2. **Crossref API** (busca bibliográfica primária)
  3. **OpenAlex API** (segunda opinião)
  4. **Semantic Scholar API** (terceira opinião com alta cobertura em Computação/arXiv)
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
Copie `.env.example` para `.env` e informe sua `GEMINI_API_KEY` (Google AI Studio):
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
