# Corretor de Redações ENEM

Fundação de um protótipo Django para correção de redações do ENEM. Esta etapa contém somente a arquitetura e as configurações iniciais; ainda não há funcionalidades de correção.

## Arquitetura

- `config/`: configuração global, URLs e pontos de entrada dos servidores WSGI/ASGI.
- `redacoes/`: aplicação de domínio que concentrará redações e correções nas próximas etapas.
- `templates/`: templates compartilhados; `base.html` carrega Bootstrap e define blocos reutilizáveis.
- `redacoes/templates/redacoes/`: templates específicos da aplicação, isolados por namespace.
- `static/`: CSS, JavaScript e imagens mantidos pelo projeto.
- `media/`: arquivos enviados por usuários durante o desenvolvimento.

SQLite foi escolhido por não exigir um servidor de banco separado e ser adequado ao protótipo. Bootstrap é carregado por CDN para manter a configuração leve, sem adicionar Node.js. Configurações sensíveis e variáveis por ambiente ficam em `.env`, carregadas por `python-dotenv`.

## Preparação no Windows (PowerShell)

É necessário ter Python 3.12 ou compatível instalado e disponível como `python`.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python manage.py migrate
python manage.py runserver
```

Antes de usar fora do ambiente local, substitua `DJANGO_SECRET_KEY` no `.env` e desative `DJANGO_DEBUG`.

Acesse `http://127.0.0.1:8000/`. O painel administrativo está configurado em `http://127.0.0.1:8000/admin/`.

## Camada de dados

O modelo `Redacao` representa a entrada original e reserva campos para os resultados das futuras etapas de processamento:

- `tema`: título ou assunto da proposta, com no mínimo 5 e no máximo 255 caracteres.
- `imagem`: imagem opcional da redação, armazenada por ano e mês e limitada a 10 MB.
- `texto_original`: texto fornecido diretamente pelo usuário, antes de qualquer processamento.
- `texto_transcrito`: texto extraído da imagem pelo Google Cloud Vision.
- `texto_revisado`: versão da transcrição confirmada manualmente pelo usuário.
- `resultado_json`: estrutura flexível para futuros resultados detalhados, iniciada como objeto vazio.
- `status`: estado do fluxo (`enviada`, `processando`, `concluida` ou `erro`).
- `criada_em`: data e hora de criação, preenchidas automaticamente.
- `atualizada_em`: data e hora da última alteração, atualizadas automaticamente.

Uma redação precisa conter uma imagem, um texto original ou ambos. O formulário inicial expõe apenas os campos de entrada; a transcrição é exibida na página de revisão.

## Interface

A página inicial usa Bootstrap 5 e concentra orientação e envio em uma única tela responsiva. Em telas grandes, instruções e formulário ficam lado a lado; em celulares, os blocos são empilhados para preservar legibilidade e áreas de toque.

O formulário aceita imagem, texto ou ambos. A pré-visualização ocorre localmente; depois do envio, imagens válidas passam pelo OCR. Após o processamento, a aplicação redireciona para a página de revisão; entradas inválidas permanecem preenchidas e apresentam os erros junto aos campos. O contador do textarea é apenas uma ajuda visual e não altera o conteúdo.

## Fluxo atual

1. A página inicial (`/`) exibe o formulário de envio.
2. Um envio válido cria a redação no SQLite.
3. Quando existe imagem, o serviço chama `DOCUMENT_TEXT_DETECTION` e salva o resultado em `texto_transcrito`.
4. O navegador é redirecionado para `/redacoes/<id>/revisao/`.
5. A revisão apresenta a imagem, o texto OCR somente para leitura e uma cópia editável.
6. `Confirmar texto` salva a versão humana em `texto_revisado` e preserva `texto_transcrito`.

Um envio inválido não cria registro nem redireciona; a página inicial reapresenta o formulário com as mensagens de validação. A revisão permite editar somente `texto_revisado` e retorna 404 para IDs inexistentes. A avaliação do Gemini ocorre apenas depois da confirmação humana.

## Revisão da transcrição

A revisão coloca imagem e OCR ao lado do campo editável em telas grandes e empilha os blocos em telas menores. O OCR é exibido como referência imutável; o textarea começa com `texto_revisado` quando já existe ou, na primeira visita, com uma cópia de `texto_transcrito`.

O botão `Confirmar texto` exige conteúdo não vazio, atualiza `texto_revisado` e usa POST–Redirect–GET. Assim, atualizar a página não repete o envio, correções confirmadas reaparecem no textarea e o resultado bruto do OCR continua disponível para auditoria. Depois de salvar, a view chama o serviço Gemini; não há nova chamada ao Vision.

## Google Cloud Vision OCR

O acesso à API fica isolado em `redacoes/services/vision_service.py`. A view não importa classes do cliente Google nem monta requisições: ela apenas chama `extrair_texto_documento()` e persiste o resultado.

### Autenticação

1. Crie ou selecione um projeto no Google Cloud, habilite faturamento e ative a Cloud Vision API.
2. Em desenvolvimento, prefira Application Default Credentials (ADC) com `gcloud auth application-default login`.
3. Em produção no Google Cloud, associe uma conta de serviço ao recurso de execução.
4. Se uma chave JSON for indispensável, salve-a fora do Git e indique seu caminho em `GOOGLE_APPLICATION_CREDENTIALS` no `.env`.

Exemplo:

```env
GOOGLE_APPLICATION_CREDENTIALS=credentials/google-vision.json
```

ADC procura primeiro essa variável, depois as credenciais locais criadas pelo `gcloud` e, por fim, uma conta de serviço associada ao ambiente. Chaves JSON de contas de serviço exigem proteção e rotação; identidades associadas ou federadas são preferíveis. Consulte a [documentação oficial de autenticação](https://docs.cloud.google.com/docs/authentication/application-default-credentials).

### Tratamento de erros

- Credenciais ausentes ou inválidas geram um erro específico de autenticação.
- Cota esgotada gera um erro específico de limite de uso.
- Falhas de transporte, indisponibilidade e tentativas esgotadas recebem uma mensagem genérica e segura.
- Cada chamada possui timeout de 30 segundos para não bloquear indefinidamente a requisição web.
- Erros retornados dentro da resposta do Vision são registrados no servidor, sem expor detalhes internos na tela.
- Falha de OCR preserva a redação e muda seu status para `erro`.
- Uma resposta válida sem texto não é exceção: o status fica `concluida` e a interface informa que nada foi reconhecido.

### Limites

O projeto restringe uploads a 10 MB. A Cloud Vision documenta limite de 20 MB por arquivo de imagem e 10 MB para o objeto JSON; imagens codificadas podem crescer aproximadamente 37%. As cotas padrão documentadas incluem 1.800 requisições por minuto e 1.800 detecções de texto por minuto, compartilhadas no projeto e sujeitas a alteração ou ajuste. Cada chamada também pode gerar cobrança. Consulte sempre a [página atual de cotas e limites](https://docs.cloud.google.com/vision/quotas) e o painel do projeto.

## Construção do prompt de avaliação

`redacoes/services/prompt_builder.py` apenas constrói e valida o contrato textual de uma futura avaliação. O módulo não importa SDK de IA, não escolhe modelo e não realiza chamadas externas.

O prompt foi dividido em seções com responsabilidades explícitas:

- **Hierarquia e papel:** limita a IA a uma avaliação pedagógica e impede que se apresente como corretor oficial do Inep.
- **Contexto:** define o gênero dissertativo-argumentativo e o objetivo da tarefa, reduzindo interpretações ambíguas.
- **Competências e escala:** fixa as cinco competências e somente os níveis 0, 40, 80, 120, 160 e 200, conforme a [Cartilha do Participante do Enem 2025](https://www.gov.br/inep/pt-br/centrais-de-conteudo/acervo-linha-editorial/publicacoes-institucionais/avaliacoes-e-exames-da-educacao-basica/redacao-do-enem-2025-cartilha-do-a-participante).
- **Situações de nota zero:** exige distinção entre o que o texto permite observar e o que depende de imagem, linhas oficiais ou textos motivadores ausentes.
- **Anti-alucinação:** obriga citações literais, listas vazias quando não há evidência e declaração explícita de limitações.
- **Proteção contra prompt injection:** serializa tema e redação como dados não confiáveis e proíbe obedecer a comandos encontrados dentro deles.
- **Contrato JSON:** define chaves, tipos, enumerações, cinco competências, decomposição da intervenção e ausência de texto fora do JSON.
- **Autoverificação:** pede uma checagem silenciosa de estrutura, notas, soma e evidências antes da resposta.
- **Validação local:** rejeita Markdown, JSON inválido, chaves extras, schema incompatível, quantidade ou ordem errada de competências, notas fora da escala, soma incorreta e citações inexistentes.

`construir_prompt_correcao(tema, redacao)` limita e normaliza as entradas antes de montar o prompt. `validar_resposta_correcao(resposta, redacao_original)` devolve um dicionário somente quando a resposta cumpre o contrato. Quando a redação não puder ser avaliada com responsabilidade, o contrato exige notas nulas, total nulo e justificativa de impedimento; isso evita fabricar precisão.

## Serviço Gemini

`redacoes/services/gemini_service.py` é a única camada que importa `google-genai`. Sua função pública `avaliar_redacao_com_gemini(tema, redacao)` lê `GEMINI_API_KEY` e `GEMINI_MODEL`, constrói o prompt, envia a solicitação, recebe o texto, converte o JSON pelo validador local e devolve somente um dicionário aprovado.

Configuração local:

```env
GEMINI_API_KEY=troque-pela-chave-do-gemini
GEMINI_MODEL=gemini-3.6-flash
```

A chave é lida no momento da chamada, nunca registrada e permanece no `.env`, que não entra no Git. O modelo também vem do ambiente para permitir troca sem alteração de código; `gemini-3.6-flash` é apenas o padrão estável atual. O serviço rejeita modelos com caracteres inesperados.

A geração usa temperatura zero, uma única candidata, até 16.384 tokens de saída, MIME `application/json` e timeout de 60 segundos. Não é enviado um segundo schema pela configuração do SDK porque o contrato já está no prompt; a resposta ainda passa pelo validador estrito, que é a autoridade final.

Erros são separados em configuração, entrada, API e resposta. Códigos 401/403 indicam chave ou permissão, 404 indica modelo, 429 indica cota, e os demais recebem mensagem genérica. Respostas vazias, não textuais, JSON inválido ou estrutura incompatível são rejeitadas. Prompt, redação, chave e resposta bruta não são gravados nos logs.

A view apenas chama `avaliar_redacao_com_gemini()` e persiste o dicionário retornado em `resultado_json`. O texto revisado é salvo antes da rede; se a API falhar, ele permanece salvo. Qualquer avaliação anterior é limpa antes da nova chamada, evitando associar uma nota antiga a um texto alterado. A chamada é síncrona neste protótipo; para maior volume, o próximo passo arquitetural seria uma fila de tarefas, fora do escopo atual.

## Comandos úteis

```powershell
python manage.py check
python manage.py test
python manage.py collectstatic --noinput
```
