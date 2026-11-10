# Corretor de Redações ENEM

Projeto feito com Django para enviar e corrigir redações do ENEM.

É possível enviar uma imagem ou digitar o texto. As imagens são convertidas em texto pelo OCR.space e a correção é feita pela API do Gemini.

## Tecnologias

- Python
- Django
- Bootstrap
- SQLite
- OCR.space
- Gemini API

## Como instalar

Crie e ative o ambiente virtual:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Instale as dependências:

```powershell
pip install -r requirements.txt
```

Crie o arquivo `.env` usando o exemplo:

```powershell
Copy-Item .env.example .env
```

O `.env` guarda só as configurações do Django. As chaves das APIs são configuradas no admin (veja abaixo).

Prepare o banco de dados:

```powershell
python manage.py migrate
```

Inicie o projeto:

```powershell
python manage.py runserver
```

Acesse no navegador:

```text
http://127.0.0.1:8000/
```

## Admin

Para criar um usuário administrador:

```powershell
python manage.py createsuperuser
```

Depois acesse:

```text
http://127.0.0.1:8000/admin/
```

### Configurar as APIs

As chaves e os parâmetros das duas APIs ficam no admin, em **Redações > Configuração das APIs**:

- **Gemini** (correção): chave da API.
- **OCR.space** (leitura de imagens): chave da API.

Sem a chave, a correção e o OCR não funcionam. Modelo, endereço, timeouts e demais parâmetros ficam no código (`redacoes/services/ai_service.py` e `ocr_service.py`). A chave nunca é exibida depois de salva; para trocá-la, digite a nova; para apagá-la, marque "Remover a chave". Alterações valem na hora, sem reiniciar o servidor.

## Observações

- A imagem deve ter no máximo 1 MB.
- Não envie dados pessoais na redação.
- A nota é apenas uma estimativa e pode ser diferente da nota oficial.
