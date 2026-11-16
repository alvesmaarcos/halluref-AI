# Relatório de Auditoria e Detecção de Alucinações Bibliográficas

- **Arquivo Analisado:** `sample_references.bib` (BIB)
- **Data/Hora da Auditoria:** `2026-11-10T15:42:56.155226+00:00`

## 1. Resumo Quantitativo (RF06)

| Métrica | Quantidade | Percentual |
| :--- | :---: | :---: |
| **Total Analisado** | **8** | 100.0% |
| **Total Válido (VÁLIDA)** | 1 | 12.5% |
| **Total Suspeito (SUSPEITA - Revisar)** | 3 | 37.5% |
| **Total Alucinado (ALUCINADA)** | 4 | 50.0% |

---

## 2. Matriz Geral de Vereditos

| # | Título Citado | Ano | DOI Citado | Similaridade | Autoria | Status Final | Taxonomia |
| :-: | :--- | :-: | :--- | :---: | :---: | :---: | :--- |
| 1 | Deep learning | 2015 | `10.1038/nature14539` | 100.0% | ALTA | **VÁLIDA** | Nenhuma (Referência Íntegra) |
| 2 | Quantum Hyper-Dimensional Self-Correcting Transformers for Autono... | 2024 | — | 57.6% | SEM_INTERSECAO | **ALUCINADA** | Invenção Total (Ghost Reference) |
| 3 | Attention Is All You Need | 2017 | — | 100.0% | SEM_INTERSECAO | **ALUCINADA** | Referência Quimera (Mosaico de Metadados) |
| 4 | Stochastic Meta-Gradient Alignment for Non-Euclidean Graph Halluc... | 2023 | `10.1038/s41586-099-99999-z` | 64.8% | SEM_INTERSECAO | **ALUCINADA** | Invenção de DOI (DOI Inexistente / 404) |
| 5 | Synthesizing Novel Biodegradable Polymers from Deep Marine Algae ... | 2021 | `10.1038/nature14539` | 27.9% | SEM_INTERSECAO | **ALUCINADA** | Sequestro de DOI (DOI Cruzado / Hijacked) |
| 6 | Deep learning | 2022 | — | 100.0% | ALTA | **SUSPEITA (Revisar)** | Distorção de Veículo ou Ano |
| 7 | ABNT NBR 14724: Informação e documentação — Trabalhos acadêmicos ... | 2011 | — | 74.5% | SEM_INTERSECAO | **SUSPEITA (Revisar)** | Não Verificável Automaticamente (Revisão Manual - RN05) |
| 8 | Portal Institucional de Pesquisa e Inovação da UFC (PIBITI) | 2025 | — | 57.1% | SEM_INTERSECAO | **SUSPEITA (Revisar)** | Não Verificável Automaticamente (Revisão Manual - RN05) |

---

## 3. Diagnóstico Explicativo Detalhado (RF05)

### [1] Deep learning

- **Status Final:** `VÁLIDA`
- **Classificação na Taxonomia:** Nenhuma (Referência Íntegra)
- **Diagnóstico Explicativo:** Referência íntegra validada na base Crossref: 'Deep learning' (Yann LeCun, Yoshua Bengio, Geoffrey Hinton, 2015). Similaridade de título: 100.0% (>= 85%), correspondência de autoria ALTA e ano exato confirmado.
- **Ação Recomendada:** Nenhuma ação necessária. Referência íntegra.

#### Metadados Extraídos vs. Registro Oficial Encontrado

| Campo | Citado no Documento | Registro Oficial (API) |
| :--- | :--- | :--- |
| **Título** | Deep learning | Deep learning |
| **Autores** | LeCun, Yann, Bengio, Yoshua, Hinton, Geoffrey | Yann LeCun, Yoshua Bengio, Geoffrey Hinton |
| **Ano** | 2015 | 2015 |
| **Veículo** | Nature | Nature |
| **DOI** | 10.1038/nature14539 | 10.1038/nature14539 |
| **Base / Fonte** | Documento (BIB) | Crossref |

- **Métricas (RN01–RN05):** Similaridade de Título = `100.0%` (`FORTE`) | Interseção de Autoria = `ALTA` | Status DOI = `VALIDO_CORRESPONDENTE` | Diferença Temporal = `0` ano(s) | Exceção RN05 = `Não`
- **Rastro de Consultas do Agente (Tools):**
  - `resolve_doi_tool`: DOI '10.1038/nature14539' resolvido via Crossref. Título oficial: 'Deep learning' (Similaridade: 100.0% - FORTE). Status DOI: VALIDO_CORRESPONDENTE. Autoria: ALTA.

---

### [2] Quantum Hyper-Dimensional Self-Correcting Transformers for Autonomous Sub-Symbolic Reasoning in Zero-Gravity Edge Networks

- **Status Final:** `ALUCINADA`
- **Classificação na Taxonomia:** Invenção Total (Ghost Reference)
- **Diagnóstico Explicativo:** Invenção Total (Ghost Reference — RN02): Após consulta em cascata no Crossref, OpenAlex e Semantic Scholar, nenhuma obra publicada corresponde ao título 'Quantum Hyper-Dimensional Self-Correcting Transformers for Autonomous Sub-Symbolic Reasoning in Zero-Gravity Edge Networks' (melhor similaridade encontrada: 57.6%, inferior ao limiar mínimo de 60%). Padrão típico de referência fabricada por modelo de linguagem.
- **Ação Recomendada:** Remover a referência do artigo ou substituir por uma fonte real verificada.

#### Metadados Extraídos vs. Registro Oficial Encontrado

| Campo | Citado no Documento | Registro Oficial (API) |
| :--- | :--- | :--- |
| **Título** | Quantum Hyper-Dimensional Self-Correcting Transformers for Autonomous Sub-Symbolic Reasoning in Zero-Gravity Edge Networks | A Self-Correcting Agentic AI Framework for Autonomous Reasoning and Decision-Making |
| **Autores** | Almeida, Lucas, Ferraz, Beatriz, Montebello, Ricardo | Vaibhav Gajananrao Ingole |
| **Ano** | 2024 | 2026 |
| **Veículo** | Journal of Advanced Synthetic Intelligence Research | International Journal of Engineering and Creative Science |
| **DOI** | — | 10.66631/ijecs.2026.9.11.5 |
| **Base / Fonte** | Documento (BIB) | Crossref |

- **Métricas (RN01–RN05):** Similaridade de Título = `57.6%` (`BAIXA`) | Interseção de Autoria = `SEM_INTERSECAO` | Status DOI = `NAO_INFORMADO` | Diferença Temporal = `2` ano(s) | Exceção RN05 = `Não`
- **Rastro de Consultas do Agente (Tools):**
  - `search_crossref_tool`: Crossref: 10 resultado(s). Melhor: 'A Self-Correcting Agentic AI Framework for Autonomous Reasoning and Decision-Making' (Similaridade: 57.6% [BAIXA], Autoria: SEM_INTERSECAO, Ano oficial: 2026).
  - `search_openalex_tool`: OpenAlex: 5 resultado(s). Melhor: 'The Incommensurability of Error and Nonsense: An AI Hallucination Interception and Creativity Blueprint' (Similaridade: 43.8% [BAIXA], Autoria: SEM_INTERSECAO, Ano oficial: None).
  - `search_semantic_scholar_tool`: Semantic Scholar: Nenhum resultado retornado para 'Quantum Hyper-Dimensional Self-Correcting Transformers for Autonomous Sub-Symbolic Reasoning in Zero-Gravity Edge Networks'.

---

### [3] Attention Is All You Need

- **Status Final:** `ALUCINADA`
- **Classificação na Taxonomia:** Referência Quimera (Mosaico de Metadados)
- **Diagnóstico Explicativo:** Referência Quimera / Atribuição Falsa de Autoria (RN03): O título 'Attention Is All You Need' existe na base OpenAlex (similaridade de 100.0%), mas pertence aos autores [Ashish Vaswani, Noam Shazeer, Niki Parmar, Jakob Uszkoreit, Llion Jones, Aidan N. Gomez, Łukasz Kaiser, Illia Polosukhin] (2017), e não aos autores [Pereira, Carlos Eduardo, Oliveira, Mariana Souza, Santos, Roberto] (2017) citados no documento (0% de interseção nos sobrenomes).
- **Ação Recomendada:** Remover a referência do artigo ou substituir por uma fonte real verificada.

#### Metadados Extraídos vs. Registro Oficial Encontrado

| Campo | Citado no Documento | Registro Oficial (API) |
| :--- | :--- | :--- |
| **Título** | Attention Is All You Need | Attention Is All You Need |
| **Autores** | Pereira, Carlos Eduardo, Oliveira, Mariana Souza, Santos, Roberto | Ashish Vaswani, Noam Shazeer, Niki Parmar, Jakob Uszkoreit, Llion Jones, Aidan N. Gomez, Łukasz Kaiser, Illia Polosukhin |
| **Ano** | 2017 | 2017 |
| **Veículo** | Advances in Neural Information Processing Systems | arXiv (Cornell University) |
| **DOI** | — | 10.48550/arxiv.1706.03762 |
| **Base / Fonte** | Documento (BIB) | OpenAlex |

- **Métricas (RN01–RN05):** Similaridade de Título = `100.0%` (`FORTE`) | Interseção de Autoria = `SEM_INTERSECAO` | Status DOI = `NAO_INFORMADO` | Diferença Temporal = `0` ano(s) | Exceção RN05 = `Não`
- **Rastro de Consultas do Agente (Tools):**
  - `search_crossref_tool`: Crossref: 10 resultado(s). Melhor: 'Attention Is All You Need' (Similaridade: 100.0% [FORTE], Autoria: SEM_INTERSECAO, Ano oficial: 2025).
  - `search_openalex_tool`: OpenAlex: 5 resultado(s). Melhor: 'Attention Is All You Need' (Similaridade: 100.0% [FORTE], Autoria: SEM_INTERSECAO, Ano oficial: 2017).
  - `search_semantic_scholar_tool`: Semantic Scholar: Nenhum resultado retornado para 'Attention Is All You Need'.

---

### [4] Stochastic Meta-Gradient Alignment for Non-Euclidean Graph Hallucination Suppression

- **Status Final:** `ALUCINADA`
- **Classificação na Taxonomia:** Invenção de DOI (DOI Inexistente / 404)
- **Diagnóstico Explicativo:** Invenção de DOI e Obra Fantasma (RN01 Critério 1): O DOI citado (10.1038/s41586-099-99999-z) retornou erro '404 Not Found' nas APIs do Crossref e do doi.org (não está registrado em nenhuma agência), e a busca textual pelo título 'Stochastic Meta-Gradient Alignment for Non-Euclidean Graph Hallucination Suppression' também não encontrou correspondência válida com autoria compatível (melhor similaridade bruta: 64.8%).
- **Ação Recomendada:** Remover a referência do artigo ou substituir por uma fonte real verificada.

#### Metadados Extraídos vs. Registro Oficial Encontrado

| Campo | Citado no Documento | Registro Oficial (API) |
| :--- | :--- | :--- |
| **Título** | Stochastic Meta-Gradient Alignment for Non-Euclidean Graph Hallucination Suppression | ReGA: Zero-Overhead Graph Alignment for Structural Hallucination Detection Without Generation |
| **Autores** | Machado, Henrique, Tavares, Fernanda | Valentin Noël, Elimane Yassine Seidou |
| **Ano** | 2023 | 2026 |
| **Veículo** | IEEE Transactions on Fictional Computing | Companion Proceedings of the ACM Web Conference 2026 |
| **DOI** | 10.1038/s41586-099-99999-z | 10.1145/3774905.3794657 |
| **Base / Fonte** | Documento (BIB) | Crossref |

- **Métricas (RN01–RN05):** Similaridade de Título = `64.8%` (`PARCIAL`) | Interseção de Autoria = `SEM_INTERSECAO` | Status DOI = `INEXISTENTE_404` | Diferença Temporal = `3` ano(s) | Exceção RN05 = `Não`
- **Rastro de Consultas do Agente (Tools):**
  - `resolve_doi_tool`: DOI '10.1038/s41586-099-99999-z' retornou 404 Not Found no Crossref e no doi.org (DOI Inexistente - RN01 Critério 1).
  - `search_crossref_tool`: Crossref: 10 resultado(s). Melhor: 'ReGA: Zero-Overhead Graph Alignment for Structural Hallucination Detection Without Generation' (Similaridade: 64.8% [PARCIAL], Autoria: SEM_INTERSECAO, Ano oficial: 2026).
  - `search_openalex_tool`: OpenAlex: 5 resultado(s). Melhor: 'Transductive meta-learning with enhanced feature ensemble for few-shot semantic segmentation' (Similaridade: 46.6% [BAIXA], Autoria: SEM_INTERSECAO, Ano oficial: 2024).
  - `search_semantic_scholar_tool`: Semantic Scholar: Nenhum resultado retornado para 'Stochastic Meta-Gradient Alignment for Non-Euclidean Graph Hallucination Suppression'.

---

### [5] Synthesizing Novel Biodegradable Polymers from Deep Marine Algae Extracts

- **Status Final:** `ALUCINADA`
- **Classificação na Taxonomia:** Sequestro de DOI (DOI Cruzado / Hijacked)
- **Diagnóstico Explicativo:** Sequestro de DOI (DOI Cruzado - RN01 Critério 2): O DOI informado (10.1038/nature14539) é válido na base Crossref, porém pertence a uma obra completamente diferente: 'Deep learning' (Yann LeCun, Yoshua Bengio, Geoffrey Hinton, 2015). A similaridade entre o título citado ('Synthesizing Novel Biodegradable Polymers from Deep Marine Algae Extracts') e o título oficial vinculado ao DOI é de apenas 27.9% (< 60%).
- **Ação Recomendada:** Remover a referência do artigo ou substituir por uma fonte real verificada.

#### Metadados Extraídos vs. Registro Oficial Encontrado

| Campo | Citado no Documento | Registro Oficial (API) |
| :--- | :--- | :--- |
| **Título** | Synthesizing Novel Biodegradable Polymers from Deep Marine Algae Extracts | Deep learning |
| **Autores** | Ribeiro, Gustavo, Mendes, Camila | Yann LeCun, Yoshua Bengio, Geoffrey Hinton |
| **Ano** | 2021 | 2015 |
| **Veículo** | International Journal of Marine Chemistry | Nature |
| **DOI** | 10.1038/nature14539 | 10.1038/nature14539 |
| **Base / Fonte** | Documento (BIB) | Crossref |

- **Métricas (RN01–RN05):** Similaridade de Título = `27.9%` (`BAIXA`) | Interseção de Autoria = `SEM_INTERSECAO` | Status DOI = `CRUZADO_HIJACKED` | Diferença Temporal = `6` ano(s) | Exceção RN05 = `Não`
- **Rastro de Consultas do Agente (Tools):**
  - `resolve_doi_tool`: DOI '10.1038/nature14539' resolvido via Crossref. Título oficial: 'Deep learning' (Similaridade: 27.9% - BAIXA). Status DOI: CRUZADO_HIJACKED. Autoria: SEM_INTERSECAO.

---

### [6] Deep learning

- **Status Final:** `SUSPEITA (Revisar)`
- **Classificação na Taxonomia:** Distorção de Veículo ou Ano
- **Diagnóstico Explicativo:** Distorção Temporal (RN04): O artigo 'Deep learning' e seus autores coincidem com o registro oficial na base Crossref (similaridade de 100.0%), porém o ano citado no documento (2022) diverge em 7 anos do ano oficial de publicação (2015), excedendo a tolerância máxima de 2 anos.
- **Ação Recomendada:** Verificar manualmente o trecho extraído ou corrigir pequenos erros de metadados.

#### Metadados Extraídos vs. Registro Oficial Encontrado

| Campo | Citado no Documento | Registro Oficial (API) |
| :--- | :--- | :--- |
| **Título** | Deep learning | Deep learning |
| **Autores** | LeCun, Yann, Bengio, Yoshua, Hinton, Geoffrey | Yann LeCun, Yoshua Bengio, Geoffrey Hinton |
| **Ano** | 2022 | 2015 |
| **Veículo** | Nature | Nature |
| **DOI** | — | 10.1038/nature14539 |
| **Base / Fonte** | Documento (BIB) | Crossref |

- **Métricas (RN01–RN05):** Similaridade de Título = `100.0%` (`FORTE`) | Interseção de Autoria = `ALTA` | Status DOI = `NAO_INFORMADO` | Diferença Temporal = `7` ano(s) | Exceção RN05 = `Não`
- **Rastro de Consultas do Agente (Tools):**
  - `search_crossref_tool`: Crossref: 10 resultado(s). Melhor: 'Deep learning' (Similaridade: 100.0% [FORTE], Autoria: ALTA, Ano oficial: 2015).

---

### [7] ABNT NBR 14724: Informação e documentação — Trabalhos acadêmicos — Apresentação

- **Status Final:** `SUSPEITA (Revisar)`
- **Classificação na Taxonomia:** Não Verificável Automaticamente (Revisão Manual - RN05)
- **Diagnóstico Explicativo:** Exceção de Escopo (RN05 — Norma técnica (ISO/ABNT/NBR/IEEE) — RN05): A referência 'ABNT NBR 14724: Informação e documentação — Trabalhos acadêmicos — Apresentação' não foi localizada nas APIs indexadas de artigos científicos (Crossref, OpenAlex e Semantic Scholar), mas apresenta características de literatura cinzenta, norma técnica, legislação, livro local ou página web. Classificada como Não Verificável Automaticamente para revisão manual.
- **Ação Recomendada:** Verificar manualmente o trecho extraído ou corrigir pequenos erros de metadados.

#### Metadados Extraídos vs. Registro Oficial Encontrado

| Campo | Citado no Documento | Registro Oficial (API) |
| :--- | :--- | :--- |
| **Título** | ABNT NBR 14724: Informação e documentação — Trabalhos acadêmicos — Apresentação | Apresentação de trabalhos acadêmicos conforme as normas da ABNT |
| **Autores** | Associação Brasileira de Normas Técnicas | Helen Rose Flores de Flores, Romilda Aparecida Teofano |
| **Ano** | 2011 | 2007 |
| **Veículo** | ABNT | Lume (Universidade Federal do Rio Grande do Sul) |
| **DOI** | — | — |
| **Base / Fonte** | Documento (BIB) | OpenAlex |

- **Métricas (RN01–RN05):** Similaridade de Título = `74.5%` (`PARCIAL`) | Interseção de Autoria = `SEM_INTERSECAO` | Status DOI = `NAO_INFORMADO` | Diferença Temporal = `4` ano(s) | Exceção RN05 = `Sim (Norma técnica (ISO/ABNT/NBR/IEEE) — RN05)`
- **Rastro de Consultas do Agente (Tools):**
  - `search_crossref_tool`: Crossref: 5 resultado(s). Melhor: 'Estrutura e formatação de trabalhos acadêmicos: compilação e discussão das normas ABNT' (Similaridade: 64.2% [PARCIAL], Autoria: SEM_INTERSECAO, Ano oficial: 2019).
  - `search_openalex_tool`: OpenAlex: 5 resultado(s). Melhor: 'Apresentação de trabalhos acadêmicos conforme as normas da ABNT' (Similaridade: 74.5% [PARCIAL], Autoria: SEM_INTERSECAO, Ano oficial: 2007).
  - `search_semantic_scholar_tool`: Semantic Scholar: Nenhum resultado retornado para 'ABNT NBR 14724: Informação e documentação — Trabalhos acadêmicos — Apresentação'.

---

### [8] Portal Institucional de Pesquisa e Inovação da UFC (PIBITI)

- **Status Final:** `SUSPEITA (Revisar)`
- **Classificação na Taxonomia:** Não Verificável Automaticamente (Revisão Manual - RN05)
- **Diagnóstico Explicativo:** Exceção de Escopo (RN05 — Página web / recurso online (@misc / URL) — RN05): A referência 'Portal Institucional de Pesquisa e Inovação da UFC (PIBITI)' não foi localizada nas APIs indexadas de artigos científicos (Crossref, OpenAlex e Semantic Scholar), mas apresenta características de literatura cinzenta, norma técnica, legislação, livro local ou página web. Classificada como Não Verificável Automaticamente para revisão manual.
- **Ação Recomendada:** Verificar manualmente o trecho extraído ou corrigir pequenos erros de metadados.

#### Metadados Extraídos vs. Registro Oficial Encontrado

| Campo | Citado no Documento | Registro Oficial (API) |
| :--- | :--- | :--- |
| **Título** | Portal Institucional de Pesquisa e Inovação da UFC (PIBITI) | Tendencias de reorganização institucional da pesquisa agricola |
| **Autores** | Universidade Federal do Ceará | Debora Luz de Mello |
| **Ano** | 2025 | 2021 |
| **Veículo** | Disponível em: https://www.ufc.br | Universidade Estadual de Campinas |
| **DOI** | — | 10.47749/t/unicamp.1995.83982 |
| **Base / Fonte** | Documento (BIB) | Crossref |

- **Métricas (RN01–RN05):** Similaridade de Título = `57.1%` (`BAIXA`) | Interseção de Autoria = `SEM_INTERSECAO` | Status DOI = `NAO_INFORMADO` | Diferença Temporal = `4` ano(s) | Exceção RN05 = `Sim (Página web / recurso online (@misc / URL) — RN05)`
- **Rastro de Consultas do Agente (Tools):**
  - `search_crossref_tool`: Crossref: 10 resultado(s). Melhor: 'Tendencias de reorganização institucional da pesquisa agricola' (Similaridade: 57.1% [BAIXA], Autoria: SEM_INTERSECAO, Ano oficial: 2021).
  - `search_openalex_tool`: OpenAlex: 5 resultado(s). Melhor: 'Ações de ensino, pesquisa e extensão direcionadas a pessoas privadas de liberdade em instituições federais de educação superior' (Similaridade: 44.8% [BAIXA], Autoria: SEM_INTERSECAO, Ano oficial: 2024).
  - `search_semantic_scholar_tool`: Semantic Scholar: Nenhum resultado retornado para 'Portal Institucional de Pesquisa e Inovação da UFC (PIBITI)'.

---
