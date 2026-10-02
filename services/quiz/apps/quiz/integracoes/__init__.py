"""Integrações de aquisição e CRM (GA4, Meta, TikTok, Klaviyo, ActiveCampaign).

Cada serviço só liga quando as variáveis de ambiente dele existem. O modelo
`IntegracaoEnvio` mora em `integracoes/models.py` (app_label "quiz") e é
carregado por quem o usa, sem tocar em `apps/quiz/models.py`.
"""
