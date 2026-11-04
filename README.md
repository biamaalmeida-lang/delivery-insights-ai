# Delivery Insights AI

Protótipo independente de IA aplicada à experiência de clientes de delivery: importa CSV/Excel, classifica comentários por meio de uma API de linguagem, gera um dashboard de qualidade e um plano de ação. O pacote contém dados **totalmente fictícios**.

## Como executar no computador

1. Instale o **Python 3.12**.
2. Extraia o ZIP e abra o terminal dentro da pasta.
3. Crie um ambiente virtual (opcional): `python -m venv .venv` e ative-o.
4. Instale dependências: `python -m pip install -r requirements.txt`.
5. Inicie: `python -m streamlit run app.py`.
6. Abra a URL local exibida pelo Streamlit.

Se não tiver uma chave de API, selecione **Demonstração classificada** e visualize o dashboard e as análises. Isso usa *resultados previamente classificados*, sem alegar que a IA foi executada em tempo real.

## Como publicar sem Replit

1. Crie um repositório no GitHub e envie os arquivos desta pasta (pode usar a opção **Add file → Upload files** na interface web).
2. Acesse https://share.streamlit.io/ e selecione **Create app**.
3. Escolha o repositório, branch `main` e arquivo principal **app.py**.
4. Clique em **Deploy**. O Streamlit instalará as dependências listadas em `requirements.txt`.
5. Para habilitar a IA, abra as configurações da aplicação e adicione em Secrets: `OPENAI_API_KEY = "SUA_CHAVE"`.

**Jamais** coloque uma chave verdadeira em um arquivo público do GitHub. Se preferir, informe uma chave no campo da barra lateral durante a sessão. Chamadas à API podem gerar custos.

## Como usar

- **Demonstração classificada:** o aplicativo mostra as 120 avaliações com classificações previamente geradas.
- **Demonstração sem rótulos:** importe a base original e teste a classificação real via API.
- **Enviar minha planilha:** CSV (vírgula ou ponto e vírgula) ou XLSX, máximo 10 MB e 3.000 linhas.
- **Coluna obrigatória:** apenas o texto do comentário. Restaurante, nota, data, tempo e valor são opcionais.
- **Avaliação do modelo:** importe `samples/gabarito_30.csv` e veja a taxa de concordância da classificação, após classificar as linhas correspondentes.
- **Edição humana:** você pode rever categorias e exportar Excel ou CSV.

A análise por IA processa até 200 comentários por clique, em lotes pequenos; repetir a análise ou mudar de fonte pode consumir mais tokens. Esta versão não possui armazenamento persistente: dados e alterações permanecem na sessão do navegador enquanto ela estiver ativa.

## Limitações e segurança

- Comentários enviados para a API deixam a aplicação e são processados pelo fornecedor do modelo. **Não envie dados pessoais ou sigilosos.**
- A classificação pode errar ou ignorar ambiguidades; revise os rótulos.
- O ranking de problemas conta apenas o **problema principal** por avaliação (não secundários).
- O conjunto de demonstração e o gabarito são sintéticos; não servem para provar resultados no mundo real.
- Não há automação operacional, agentes autônomos ou integração a sistemas de restaurantes reais.
- `st.session_state` é volátil e fica associado à sessão; exporte os resultados quando necessário.

## Organização dos arquivos

```
app.py               Interface e visualizações
core.py              Leitura, normalização, análises e validação
ai_classifier.py     Integração com IA generativa (API real)
requirements.txt     Dependências
.streamlit/config.toml  Tema do aplicativo
samples/             Bases CSV fictícias e gabarito
 tests/              Testes básicos de lógica
```

Projeto criado como demonstração de portfólio, sem afiliação com iFood ou restaurantes reais.
