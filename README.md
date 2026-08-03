# Corretor de Redações ENEM

Projeto feito com Django para enviar e corrigir redações do ENEM.

É possível enviar uma imagem ou digitar o texto. As imagens são convertidas em texto pelo OCR.space e a correção é feita pela API da NVIDIA.

## Tecnologias

- Python
- Django
- Bootstrap
- SQLite
- OCR.space
- NVIDIA Build

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

Coloque suas chaves no `.env`:

```env
OCR_SPACE_API_KEY=sua-chave
NVIDIA_API_KEY=sua-chave
```

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

## Observações

- A imagem deve ter no máximo 1 MB.
- Não envie dados pessoais na redação.
- A nota é apenas uma estimativa e pode ser diferente da nota oficial.
