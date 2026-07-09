# Dashboard ReVive · Painel Unificado

Dashboard interativo com todas as campanhas Meta Ads da ReVive Assessoria, com **atualização automática todo dia às 8h + botão manual** pra atualizar quando quiser.

---

## 🎯 Setup completo — 4 passos (~30 minutos, uma única vez)

### PASSO 1 — Criar o repositório no GitHub

1. Vai em [github.com/new](https://github.com/new)
2. Nome do repositório: `painel-revive` (ou o que preferir)
3. Marca como **Público** (necessário pro GitHub Pages funcionar no plano free)
4. **Não** marque "Add a README" (você vai subir o que já está pronto)
5. Clica em **Create repository**

### PASSO 2 — Fazer upload dos arquivos

Você precisa subir **exatamente essa estrutura**:

```
painel-revive/
├── index.html                              (o dashboard inicial)
├── README.md                               (esse arquivo)
├── scripts/
│   ├── update.py                           (script que puxa dados)
│   └── template.html                       (template do dashboard)
└── .github/
    └── workflows/
        └── update-dashboard.yml            (o botão + agendamento)
```

**Como subir:**
1. Na tela do repo recém-criado, clica em **Add file → Upload files**
2. Arrasta **TODOS os arquivos** de uma vez (o GitHub preserva a estrutura de pastas)
3. Mensagem do commit: `setup inicial do painel`
4. Clica em **Commit changes**

### PASSO 3 — Gerar o token da Meta e configurar no GitHub

Essa é a parte mais crítica. O token é o que permite o GitHub puxar dados da sua conta Meta Ads.

**3a. Gerar o token no Meta Business:**

1. Acessa [business.facebook.com/settings/system-users](https://business.facebook.com/settings/system-users)
2. No menu esquerdo: **Usuários** → **Usuários do sistema**
3. Clica em **Adicionar** (canto superior direito)
4. Nome: `Dashboard Automation` — Função: **Admin do sistema** — Salvar
5. Com o usuário criado, clica em **Adicionar recursos**
6. Seleciona **Contas de anúncios** → escolhe a conta ReVive → marca **Gerenciar campanhas** e **Ver desempenho** → Salvar
7. Volta pro perfil do usuário do sistema, clica em **Gerar novo token**
8. App: seleciona qualquer app que aparecer (se não tiver, cria um em [developers.facebook.com](https://developers.facebook.com))
9. Permissões marca: **ads_read** e **ads_management**
10. Validade: **Nunca expira** ✅
11. **Copia o token que aparece** (parece uma string enorme, tipo `EAAX...`)
12. Guarda em algum lugar seguro por enquanto (bloco de notas)

**3b. Adicionar o token e o ID da conta como Secrets no GitHub:**

1. No teu repositório, vai em **Settings** (menu superior)
2. Menu esquerdo: **Secrets and variables → Actions**
3. Clica em **New repository secret**
4. Cria os dois:

| Nome | Valor |
|---|---|
| `META_TOKEN` | O token que você acabou de gerar (começa com `EAA...`) |
| `AD_ACCOUNT_ID` | `863857055025547` |

### PASSO 4 — Ativar o GitHub Pages

1. Ainda em **Settings**, menu esquerdo: **Pages**
2. Em **Source**: **Deploy from a branch**
3. Em **Branch**: **main** — pasta: **/ (root)** → Save
4. Aguarda 1-2 minutos
5. Teu painel estará em: `https://SEU-USUARIO.github.io/painel-revive/`

**Anota essa URL nos favoritos** — é a que você vai acessar todo dia.

---

## 🚀 Como usar depois de configurado

### Atualizar manualmente (o botão)

1. Vai na aba **Actions** do teu repo
2. Menu esquerdo: **Atualizar Dashboard ReVive**
3. Clica no botão **Run workflow** (canto direito) → **Run workflow** (verde)
4. Aguarda ~1 minuto (você vê o progresso na tela)
5. Quando terminar, dá refresh na URL do painel — atualizado!

### Automático

Todo dia **às 8h da manhã** (horário de Brasília), o painel atualiza sozinho. Você não precisa fazer nada. Só abrir a URL e olhar.

---

## 🔧 Quando algo der errado

**"O botão rodou mas o painel não atualizou"**
- Vai na aba Actions e clica no workflow que rodou
- Se aparecer 🔴 (vermelho), clica pra ver o erro
- Erros mais comuns:
  - **Invalid OAuth access token** → o token expirou ou está errado. Volta no passo 3a, gera outro e atualiza o secret `META_TOKEN` no GitHub
  - **Application does not have permission** → falta permissão `ads_read` no token
  - **Rate limit** → esperou muito ou muitas chamadas. Espera 30 min e tenta de novo

**"Token expirou de novo"**
- Se você marcou "Nunca expira" no passo 3a, isso não deveria acontecer
- Se marcou 60 dias por engano, o GitHub Actions vai começar a falhar depois de 2 meses. É só gerar outro e atualizar o secret.

**"Preciso mudar o horário automático"**
- Edita o arquivo `.github/workflows/update-dashboard.yml`
- Muda a linha `cron: '0 11 * * *'` (11h UTC = 8h Brasília)
- Formato cron: `minuto hora dia-mes mes dia-semana`
- Exemplo pra 3x ao dia (8h, 13h, 18h Brasília): `'0 11,16,21 * * *'`

---

## 📊 O que tem no dashboard

- **6 KPIs** no topo (total, gasto, CPA de captação e vagas)
- **Gráfico interativo** de campanhas criadas por mês (com 3 métricas alternáveis)
- **Filtro de calendário** com atalhos (7d, 30d, 90d, 6m, 1a)
- **Filtro por praça** (16 cidades) e **por tipo** (Vaga, Acidente, APPs, Seguro de vida, Renato, Yudi, Crislaine, etc)
- **Busca em tempo real** por nome/praça/tipo
- **8 ordenações**
- **Detalhe expandido** com sugestão automática (Tá bem boa / Monitorar / Precisa ajustar)
- **Link direto pro Gerenciador** em cada campanha
- **Tema claro/escuro** com preferência salva
- **Responsivo** (funciona no celular)
