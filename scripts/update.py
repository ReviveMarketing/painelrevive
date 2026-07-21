#!/usr/bin/env python3
"""
Atualiza o dashboard ReVive puxando dados da Meta Ads API.
Requer env vars: META_TOKEN e AD_ACCOUNT_ID.

VERSAO 2 - Adiciona snapshot historico embebido no HTML pra permitir
comparativos entre execucoes (hoje vs ontem, atual vs anterior).
NAO quebra a automacao existente - so adiciona features.
"""

import os
import re
import json
import sys
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime, timezone, timedelta
from collections import defaultdict

# ============================================================
# CONFIG
# ============================================================
META_TOKEN = os.environ.get('META_TOKEN', '')
AD_ACCOUNT_ID = os.environ.get('AD_ACCOUNT_ID', '')
API_VERSION = 'v20.0'
BASE_URL = f'https://graph.facebook.com/{API_VERSION}'

if not META_TOKEN or not AD_ACCOUNT_ID:
    print("ERRO: META_TOKEN e AD_ACCOUNT_ID sao obrigatorios.")
    sys.exit(1)

# ============================================================
# HELPERS API
# ============================================================
def meta_get(endpoint, params=None):
    params = params or {}
    params['access_token'] = META_TOKEN
    url = f"{BASE_URL}/{endpoint}?{urllib.parse.urlencode(params)}"
    try:
        with urllib.request.urlopen(url, timeout=30) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', errors='replace')
        print(f"HTTP {e.code} em {endpoint}: {body[:500]}")
        raise

def paginate(endpoint, params, max_pages=20):
    all_data = []
    result = meta_get(endpoint, params)
    all_data.extend(result.get('data', []))
    page = 1
    while page < max_pages and 'paging' in result and 'next' in result.get('paging', {}):
        next_url = result['paging']['next']
        try:
            with urllib.request.urlopen(next_url, timeout=30) as response:
                result = json.loads(response.read())
                all_data.extend(result.get('data', []))
                page += 1
        except Exception as e:
            print(f"Erro na paginacao pagina {page+1}: {e}")
            break
    return all_data

# ============================================================
# EXTRACTION
# ============================================================
def extract_praca(name):
    n = name.lower()
    if "fortaleza" in n: return "Fortaleza"
    if "ipatinga" in n: return "Ipatinga"
    if "brusque" in n: return "Brusque"
    if "chapec" in n: return "Chapeco"
    if "crici" in n: return "Criciuma"
    if "trombudo" in n: return "Trombudo"
    if "pouso" in n: return "Pouso Redondo"
    if "biguacu" in n or "bigua" in n: return "Biguacu"
    if "palhoca" in n or "palho" in n: return "Palhoca"
    if "sao jos" in n or "sao jose" in n: return "Sao Jose"
    if "(mg)" in n or "minas" in n: return "Minas Gerais"
    if "jvlle" in n or "joinville" in n: return "Joinville"
    if "(rsl)" in n or "rio do sul" in n: return "Rio do Sul"
    if any(k in n for k in ["(fln)","florianopolis","(flp)","(floripa)","[floripa]","flp)"]): return "Floripa"
    if "itaja" in n: return "Itajai"
    if "(bnu)" in n or "[bnu]" in n or " bnu " in n or "-bnu-" in n: return "Blumenau"
    if "(brasil)" in n: return "Brasil (geral)"
    return "Outros"

def extract_tipo(name):
    n = name.lower()
    if "vaga" in n or "[vagas]" in n or "vaga de emprego" in n: return "Vaga"
    if "seguro" in n and "vida" in n: return "Seguro de vida"
    if "acid" in n: return "Acidente"
    if "auxilio" in n or "auxílio" in n: return "Auxilio-doenca"
    if "aposent" in n: return "Aposentadoria"
    if "revisao" in n or "revisão" in n: return "Revisao INSS"
    if "bpc" in n or "loas" in n: return "BPC/LOAS"
    if "emprestimo" in n or "empréstimo" in n or "consignado" in n or "dpvat" in n: return "Emprestimo/DPVAT"
    if "cronometro" in n or "cronômetro" in n: return "Cronometro"
    if "carrossel" in n: return "Carrossel"
    if "apps" in n: return "APPs"
    if "bot" in n: return "Bot"
    if "renato" in n: return "Renato"
    if "yudi" in n: return "Yudi"
    if "crislaine" in n: return "Crislaine"
    if "corretor" in n: return "Corretores"
    return "Outros"

def parse_iso_date(iso_str):
    if not iso_str: return ""
    return iso_str.split('T')[0]

def parse_iso_to_pt(iso_str):
    if not iso_str: return ""
    meses = ["janeiro","fevereiro","março","abril","maio","junho","julho","agosto","setembro","outubro","novembro","dezembro"]
    try:
        d = iso_str.split('T')[0].split('-')
        return f"{int(d[2])} de {meses[int(d[1])-1]} de {d[0]}"
    except:
        return iso_str

def get_insights_metric(insights_data, metric_name):
    if not insights_data: return 0
    val = insights_data.get(metric_name)
    if val is None: return 0
    try: return float(val)
    except: return 0

def get_conversations_started(actions):
    if not actions: return 0
    for action in actions:
        if action.get('action_type') in ['onsite_conversion.messaging_conversation_started_7d', 'messaging_conversation_started_7d']:
            try: return int(float(action.get('value', 0)))
            except: return 0
    return 0

def get_cost_per_conversation(cost_per_action_type):
    if not cost_per_action_type: return 0
    for cpa in cost_per_action_type:
        if cpa.get('action_type') in ['onsite_conversion.messaging_conversation_started_7d', 'messaging_conversation_started_7d']:
            try: return float(cpa.get('value', 0))
            except: return 0
    return 0

# ============================================================
# SNAPSHOT HISTORY
# ============================================================
def extract_prev_snapshot(html_path):
    """
    Le o snapshot ATUAL do index.html anterior (tag 'current-snapshot-data').
    Esse dado virara o 'anterior' pro comparativo do JS nesta nova execucao.
    """
    if not os.path.exists(html_path):
        return None
    try:
        with open(html_path, 'r', encoding='utf-8') as f:
            html = f.read()
        # Le a tag 'current-snapshot-data' (que foi salva pela execucao anterior)
        m = re.search(
            r'<script id="current-snapshot-data" type="application/json">(.*?)</script>',
            html, re.DOTALL
        )
        if m:
            raw = m.group(1).strip()
            if raw and raw not in ('null', ''):
                return json.loads(raw)
        # Fallback: tenta ler tag antiga (retrocompat com versao anterior do template)
        m = re.search(
            r'<script id="prev-snapshot-data" type="application/json">(.*?)</script>',
            html, re.DOTALL
        )
        if m:
            raw = m.group(1).strip()
            if raw and raw not in ('null', ''):
                return json.loads(raw)
    except Exception as e:
        print(f"Falha ao ler snapshot anterior: {e}")
    return None

def build_snapshot(campanhas, stats, timestamp):
    """Cria snapshot dos dados atuais pra proxima execucao usar de comparativo"""
    return {
        "timestamp": timestamp,
        "totals": {
            "spent": round(stats["spent"], 2),
            "conv": stats["conv"],
            "active": stats["active"],
            "cap_spent": round(stats["cap_spent"], 2),
            "cap_conv": stats["cap_conv"],
            "vag_spent": round(stats["vag_spent"], 2),
            "vag_conv": stats["vag_conv"],
        },
        "campaigns": {
            c["id"]: {
                "spent": c["spent"],
                "conv": c["conv"],
                "cpa": c["cpa"],
                "ctr": c["ctr"],
                "freq": c["freq"],
            }
            for c in campanhas
        }
    }

# ============================================================
# FETCH & PROCESS
# ============================================================
def fetch_campaigns():
    print(f"Puxando campanhas da conta {AD_ACCOUNT_ID}...")
    fields = (
        "id,name,effective_status,created_time,updated_time,"
        "insights.date_preset(maximum){"
        "spend,frequency,ctr,cpm,reach,impressions,clicks,actions,cost_per_action_type"
        "}"
    )
    campaigns = paginate(f"act_{AD_ACCOUNT_ID}/campaigns", {
        'fields': fields,
        'limit': 100,
    })
    print(f"Total de campanhas encontradas: {len(campaigns)}")
    active_ids = [c['id'] for c in campaigns if c.get('effective_status') == 'ACTIVE']
    print(f"Buscando insights recentes (30d) de {len(active_ids)} campanhas ativas...")
    recent_insights = {}
    for i, cid in enumerate(active_ids):
        try:
            result = meta_get(f"{cid}/insights", {
                'fields': 'spend,frequency,ctr,cpm,reach,impressions,clicks,actions,cost_per_action_type',
                'date_preset': 'last_30d',
            })
            data = result.get('data', [])
            if data:
                recent_insights[cid] = data[0]
        except Exception as e:
            print(f"  falha em {cid}: {e}")
        if (i+1) % 10 == 0:
            print(f"  {i+1}/{len(active_ids)}")
    return campaigns, recent_insights

def fetch_monthly_insights(campaigns):
    """
    Puxa metricas mensais (breakdown por mes) de cada campanha que ja teve gasto.
    Retorna dict: {campaign_id: {"YYYY-MM": {"spent": x, "conv": y}, ...}}
    
    IMPORTANTE: Essa funcao adiciona ~1 chamada extra por campanha com gasto.
    Se falhar em uma campanha, continua as outras (nao quebra o fluxo).
    """
    monthly_data = {}
    # Filtra so campanhas que ja tem historico de gasto
    campaigns_with_history = []
    for c in campaigns:
        insights = c.get('insights', {}).get('data', [])
        if insights and float(insights[0].get('spend', 0) or 0) > 0:
            campaigns_with_history.append(c['id'])
    
    total = len(campaigns_with_history)
    print(f"Buscando historico mensal de {total} campanhas com gasto...")
    
    for i, cid in enumerate(campaigns_with_history):
        try:
            result = meta_get(f"{cid}/insights", {
                'fields': 'spend,actions',
                'date_preset': 'maximum',
                'time_increment': 'monthly',
                'limit': 100,
            })
            data = result.get('data', [])
            monthly = {}
            for entry in data:
                date_start = entry.get('date_start', '')
                if not date_start or len(date_start) < 7:
                    continue
                mkey = date_start[:7]  # "YYYY-MM"
                spend = float(entry.get('spend', 0) or 0)
                actions = entry.get('actions', [])
                conv = get_conversations_started(actions)
                monthly[mkey] = {
                    'spent': round(spend, 2),
                    'conv': conv
                }
            if monthly:
                monthly_data[cid] = monthly
        except Exception as e:
            print(f"  falha ao puxar mensal de {cid}: {e}")
        if (i+1) % 20 == 0:
            print(f"  {i+1}/{total}")
    print(f"Historico mensal obtido para {len(monthly_data)} campanhas")
    return monthly_data

def process_campaigns(campaigns, recent_insights, monthly_data=None):
    processed = []
    monthly_data = monthly_data or {}
    for c in campaigns:
        is_active = c.get('effective_status') == 'ACTIVE'
        insights = None
        if is_active and c['id'] in recent_insights:
            insights = recent_insights[c['id']]
        elif c.get('insights') and c['insights'].get('data'):
            insights = c['insights']['data'][0]
        spend = get_insights_metric(insights, 'spend')
        freq = get_insights_metric(insights, 'frequency')
        ctr = get_insights_metric(insights, 'ctr')
        cpm = get_insights_metric(insights, 'cpm')
        reach = int(get_insights_metric(insights, 'reach'))
        impressions = int(get_insights_metric(insights, 'impressions'))
        clicks = int(get_insights_metric(insights, 'clicks'))
        actions = insights.get('actions', []) if insights else []
        cost_per_action = insights.get('cost_per_action_type', []) if insights else []
        conv = get_conversations_started(actions)
        cpa = get_cost_per_conversation(cost_per_action)
        name = c.get('name', '')
        tipo = extract_tipo(name)
        item = {
            'id': c['id'],
            'name': name,
            'status': 'ACTIVE' if is_active else 'PAUSED',
            'spent': round(spend, 2),
            'freq': round(freq, 2),
            'ctr': round(ctr, 2),
            'cpm': round(cpm, 2),
            'reach': reach,
            'impressions': impressions,
            'clicks': clicks,
            'conv': conv,
            'cpa': round(cpa, 2),
            'created': parse_iso_to_pt(c.get('created_time', '')),
            'updated': parse_iso_to_pt(c.get('updated_time', '')),
            'created_iso': parse_iso_date(c.get('created_time', '')),
            'praca': extract_praca(name),
            'tipo': tipo,
            'mtype': 'VIDEO' if any(k in name.lower() for k in ['vídeo','video']) else 'IMAGE',
            'segment': 'vaga' if tipo == 'Vaga' else 'captacao',
        }
        # Adiciona breakdown mensal se disponivel
        if c['id'] in monthly_data:
            item['monthly'] = monthly_data[c['id']]
        processed.append(item)
    processed.sort(key=lambda x: -x['spent'])
    return processed

def compute_stats(campanhas):
    active = sum(1 for c in campanhas if c['status']=='ACTIVE')
    total_spent = sum(c['spent'] for c in campanhas)
    total_conv = sum(c['conv'] for c in campanhas)
    cap_spent = sum(c['spent'] for c in campanhas if c['segment']=='captacao')
    cap_conv = sum(c['conv'] for c in campanhas if c['segment']=='captacao')
    vag_spent = sum(c['spent'] for c in campanhas if c['segment']=='vaga')
    vag_conv = sum(c['conv'] for c in campanhas if c['segment']=='vaga')
    pracas = {}
    for c in campanhas:
        p = c['praca']
        if p not in pracas: pracas[p] = {'spent':0,'conv':0,'n':0,'active':0}
        pracas[p]['spent'] += c['spent']
        pracas[p]['conv'] += c['conv']
        pracas[p]['n'] += 1
        if c['status']=='ACTIVE': pracas[p]['active'] += 1
    for p in pracas:
        pracas[p]['cpa'] = pracas[p]['spent']/pracas[p]['conv'] if pracas[p]['conv'] else 0
    tipos = {}
    for c in campanhas:
        t = c['tipo']
        if t not in tipos: tipos[t] = {'spent':0,'conv':0,'n':0,'active':0}
        tipos[t]['spent'] += c['spent']
        tipos[t]['conv'] += c['conv']
        tipos[t]['n'] += 1
        if c['status']=='ACTIVE': tipos[t]['active'] += 1
    for t in tipos:
        tipos[t]['cpa'] = tipos[t]['spent']/tipos[t]['conv'] if tipos[t]['conv'] else 0
    by_month = defaultdict(lambda: {'spent':0,'conv':0,'n':0})
    for c in campanhas:
        iso = c.get('created_iso','')
        if iso and len(iso)>=7:
            mkey = iso[:7]
            by_month[mkey]['spent'] += c['spent']
            by_month[mkey]['conv'] += c['conv']
            by_month[mkey]['n'] += 1
    return {
        'total': len(campanhas), 'active': active, 'paused': len(campanhas)-active,
        'spent': total_spent, 'conv': total_conv,
        'cap_n': sum(1 for c in campanhas if c['segment']=='captacao'),
        'vagas_n': sum(1 for c in campanhas if c['segment']=='vaga'),
        'cap_spent': cap_spent, 'cap_conv': cap_conv,
        'vag_spent': vag_spent, 'vag_conv': vag_conv,
        'pracas': pracas, 'tipos': tipos, 'monthly': dict(by_month)
    }

# ============================================================
# HTML GENERATION
# ============================================================
def compare_info_from_snapshot(prev_snapshot, now_pt):
    """Cria mensagem informativa sobre a comparacao"""
    if not prev_snapshot or 'timestamp' not in prev_snapshot:
        return "Primeira execucao — comparativo aparecera na proxima"
    prev_ts = prev_snapshot['timestamp']
    return f"Comparado com execucao de {prev_ts}"

def generate_html(campanhas, stats, prev_snapshot, current_snapshot):
    template_path = os.path.join(os.path.dirname(__file__), 'template.html')
    with open(template_path, 'r', encoding='utf-8') as f:
        template = f.read()
    js_data = json.dumps(campanhas, ensure_ascii=False)
    pracas_sorted = sorted(stats['pracas'].items(), key=lambda x: -x[1]['spent'])
    tipos_sorted = sorted(stats['tipos'].items(), key=lambda x: -x[1]['spent'])
    monthly_sorted = dict(sorted(stats['monthly'].items()))
    now_pt = (datetime.now(timezone.utc) - timedelta(hours=3)).strftime('%d/%m/%Y %H:%M')
    compare_info = compare_info_from_snapshot(prev_snapshot, now_pt)
    prev_json = json.dumps(prev_snapshot, ensure_ascii=False) if prev_snapshot else "null"
    current_json = json.dumps(current_snapshot, ensure_ascii=False)
    replacements = {
        '{{JS_DATA}}': js_data,
        '{{PRACAS}}': json.dumps(pracas_sorted, ensure_ascii=False),
        '{{TIPOS}}': json.dumps(tipos_sorted, ensure_ascii=False),
        '{{MONTHLY}}': json.dumps(monthly_sorted, ensure_ascii=False),
        '{{AD_ACCOUNT_ID}}': AD_ACCOUNT_ID,
        '{{TOTAL}}': str(stats['total']),
        '{{ACTIVE}}': str(stats['active']),
        '{{PAUSED}}': str(stats['paused']),
        '{{SPENT}}': f'{stats["spent"]:,.0f}'.replace(',','.'),
        '{{SPENT_RAW}}': str(round(stats['spent'], 2)),
        '{{TOTAL_CONV}}': f'{stats["conv"]:,}'.replace(',','.'),
        '{{TOTAL_CONV_RAW}}': str(stats['conv']),
        '{{CAP_SPENT}}': f'{stats["cap_spent"]:,.0f}'.replace(',','.'),
        '{{VAG_SPENT}}': f'{stats["vag_spent"]:,.0f}'.replace(',','.'),
        '{{CAP_N}}': str(stats['cap_n']),
        '{{VAGAS_N}}': str(stats['vagas_n']),
        '{{CAP_CPA}}': f'{stats["cap_spent"]/stats["cap_conv"] if stats["cap_conv"] else 0:.2f}'.replace('.',','),
        '{{VAG_CPA}}': f'{stats["vag_spent"]/stats["vag_conv"] if stats["vag_conv"] else 0:.2f}'.replace('.',','),
        '{{CAP_CONV}}': f'{stats["cap_conv"]:,}'.replace(',','.'),
        '{{VAG_CONV}}': f'{stats["vag_conv"]:,}'.replace(',','.'),
        '{{UPDATE_STAMP}}': f'Atualizado em {now_pt}',
        '{{COMPARE_INFO}}': compare_info,
        '{{PREV_SNAPSHOT}}': prev_json,
        '{{CURRENT_SNAPSHOT}}': current_json,
    }
    for k, v in replacements.items():
        template = template.replace(k, v)
    return template

# ============================================================
# MAIN
# ============================================================
def main():
    print(f"[{datetime.now()}] Iniciando atualizacao...")
    output_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'index.html')
    
    # 1. Le snapshot anterior do proprio index.html (pra comparativo)
    prev_snapshot = extract_prev_snapshot(output_path)
    if prev_snapshot:
        print(f"Snapshot anterior carregado (de {prev_snapshot.get('timestamp','?')})")
    else:
        print("Nenhum snapshot anterior encontrado (primeira execucao)")
    
    # 2. Puxa dados novos
    campaigns, recent_insights = fetch_campaigns()
    
    # 2b. Puxa breakdown mensal (necessario pro filtro por periodo funcionar bem)
    monthly_data = fetch_monthly_insights(campaigns)
    
    processed = process_campaigns(campaigns, recent_insights, monthly_data)
    stats = compute_stats(processed)
    
    print(f"\nEstatisticas:")
    print(f"  Total: {stats['total']} campanhas ({stats['active']} ativas, {stats['paused']} pausadas)")
    print(f"  Captacao: R$ {stats['cap_spent']:.0f} / {stats['cap_conv']} conv")
    print(f"  Vagas: R$ {stats['vag_spent']:.0f} / {stats['vag_conv']} conv")
    print(f"  Campanhas com breakdown mensal: {sum(1 for c in processed if 'monthly' in c)}")
    
    # 3. Gera novo HTML:
    #    - Tag 'prev-snapshot-data' = snapshot ANTERIOR (JS compara com dados atuais)
    #    - Tag 'current-snapshot-data' = snapshot ATUAL (proxima execucao lera como anterior)
    now_pt = (datetime.now(timezone.utc) - timedelta(hours=3)).strftime('%d/%m/%Y %H:%M')
    current_snapshot = build_snapshot(processed, stats, now_pt)
    
    html = generate_html(processed, stats, prev_snapshot, current_snapshot)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)
    
    print(f"\n[{datetime.now()}] Dashboard atualizado: {output_path}")
    print(f"Tamanho: {len(html):,} bytes")
    print(f"Snapshot atual salvo: {len(current_snapshot['campaigns'])} campanhas")
    if prev_snapshot:
        print(f"Comparativo disponivel (snapshot de {prev_snapshot.get('timestamp','?')})")

if __name__ == '__main__':
    main()
