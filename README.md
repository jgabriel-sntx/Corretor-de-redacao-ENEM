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

Acesse `http://127.0.0.1:8000/`. Enquanto nenhuma funcionalidade for criada, a raiz retorna 404 por decisão de escopo; o painel administrativo está configurado em `http://127.0.0.1:8000/admin/`.

## Camada de dados

O modelo `Redacao` representa a entrada original e reserva campos para os resultados das futuras etapas de processamento:

- `tema`: título ou assunto da proposta, com no mínimo 5 e no máximo 255 caracteres.
- `imagem`: imagem opcional da redação, armazenada por ano e mês e limitada a 10 MB.
- `texto_original`: texto fornecido diretamente pelo usuário, antes de qualquer processamento.
- `texto_transcrito`: futura transcrição da imagem; permanece vazio até existir OCR.
- `texto_revisado`: futura versão revisada; permanece vazia até existir processamento.
- `resultado_json`: estrutura flexível para futuros resultados detalhados, iniciada como objeto vazio.
- `status`: estado do fluxo (`enviada`, `processando`, `concluida` ou `erro`).
- `criada_em`: data e hora de criação, preenchidas automaticamente.
- `atualizada_em`: data e hora da última alteração, atualizadas automaticamente.

Uma redação precisa conter uma imagem, um texto original ou ambos. O formulário inicial expõe apenas os campos de entrada; campos produzidos por processamento não são apresentados ao usuário nesta etapa.

## Interface

A página inicial usa Bootstrap 5 e concentra orientação e envio em uma única tela responsiva. Em telas grandes, instruções e formulário ficam lado a lado; em celulares, os blocos são empilhados para preservar legibilidade e áreas de toque.

O formulário aceita imagem, texto ou ambos. A imagem escolhida recebe uma pré-visualização local no navegador, sem OCR ou envio adicional. Após um cadastro válido, a aplicação salva a redação, redireciona para a página inicial e exibe uma mensagem de sucesso; entradas inválidas permanecem preenchidas e apresentam os erros junto aos campos. O contador do textarea é apenas uma ajuda visual e não altera o conteúdo.

## Comandos úteis

```powershell
python manage.py check
python manage.py test
python manage.py collectstatic --noinput
```
