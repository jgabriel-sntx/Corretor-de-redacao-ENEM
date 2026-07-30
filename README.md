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

## Comandos úteis

```powershell
python manage.py check
python manage.py test
python manage.py collectstatic --noinput
```
