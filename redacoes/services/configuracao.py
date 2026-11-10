def professor_do_aluno(aluno):
    """Professor dono da turma do aluno (ou None se ele não tem turma)."""
    turma = getattr(aluno, "turma", None)
    return turma.professor if turma else None


def chave_gemini(aluno) -> str:
    """Chave do Gemini cadastrada pelo professor da turma do aluno."""
    professor = professor_do_aluno(aluno)
    return (professor.gemini_api_key if professor else "").strip()


def chave_ocr(aluno) -> str:
    """Chave do OCR.space cadastrada pelo professor da turma do aluno."""
    professor = professor_do_aluno(aluno)
    return (professor.ocr_api_key if professor else "").strip()
