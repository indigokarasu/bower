#!/usr/bin/env python3
"""
Resume Bower deep scan from where it left off.
Skips Hermes and Openclaw backup folders.
Uses scans/ directory as source of truth for what was scanned.
"""
import json
import sys
import time
from pathlib import Path
from datetime import datetime, timezone
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Paths
HERMES_HOME = Path.home() / ".hermes"
BOWER_DATA = HERMES_HOME / "commons/data/ocas-bower"
TOKEN_PATH = HERMES_HOME / "google_token.json"

SCANS_DIR = BOWER_DATA / "scans"
FOLDER_INDEX = BOWER_DATA / "folder_index.json"
SCAN_PROGRESS = BOWER_DATA / "scan_progress.json"

# Folders to skip (agent system backups - not user's real Drive content)
SKIP_FOLDERS = {
    # hermes-* folders
    "1Axg8QxQ5WlDbvIxW_4Jglm4zWVG-Qudj", "1tcHNivhcpJY9zXMrFtuf4WV-tTKx1lD1", "19lJhqHgAjcg0N3x-M5FlK40gAdf6uPmj", "1i8fuFw5nqm3ABqVRVskgos97lzxnxcoe",
    "1Nruipkw44CbuKVmb9fvxJ3c3svtjjRdi", "17GFgeXttVgw-Ob4ScKCLPt7UH8We-qyU", "1Bp7eaRhsNLYZiom8NDbyH1QCg2P578VJ", "10l4dOVO5GMY7cjRLKTvNxhhnZOvA-6s0",
    "1gdXBSjwNsJ5MCohzB-3g67O5e_OggaDZ", "1uBwL8OJ-XrXaBo4Uv9niZ_Qdx3JaqWHS", "1_Uk9ElpbEkxGT0mpgAo-d6KBOk1rnnXC", "1keQ5D1p2QP_XaxaabpMw-YYZL9GOORN6",
    "1U7fjHvCaEV_TriNV6hTeg18zXCur2xQq", "1EvSC9BeUXnfGYeQjQOU83ayc-emWZcjh", "1UQSIWHWPyyDKpndYJmmqLsHX3eOWW2Pd", "1BuOyNn-FzyE0y4Isdtm-dLtg0w8TcIyd",
    "17L_kI3G8ktH5Wxl7acB3LbqpfhxLQTs-", "1Iz4moRaZ7XHHRXe9J58Y0_WZPyEkz2B0", "10xhYQgVvH5bGNR9G2DV6RuM6tFEFFDyF", "1mtcX_BnQDhavB7JflZ9UzswXa0NmeXry",
    "1PbBgEhhvnZ4n_KXj4jLrfPgHHef1Z37F", "1tG0l1bc0QwqnIwnBB2KFroNrLiTGaYNv", "1Es2PNy7YkMUR3vqIDuq5RBBTWUzX3dvw", "1LNE5aVFdOewamRREUiVeq753nFUC7-3z",
    "1bEp0H4uDLFzecudkFgD_FeuDxbnLfrod", "12HtiKh0xSiE7CXHnsKXfhji34LWcl_0u", "1RscVR0O8x4l1Q5J1yajXEZ4DVq3Dr1nt", "1_CqNE1ehht4SAWpJnipKXyssUrYC2ibU",
    "1EgtfM4VkOSVPBz4wDZvJXaypFVls2wXs", "1Lq16go6uUD4dLczYCtizW6RLIbpGt9xy", "11iSOx-xZq5JRiGkZuEikDDqlPZfZllrY", "1AlCiMqNmjoLjZO8TudPl9G-7v7wdslQk",
    "19uVVUv-KoGIAT8-5j5rvxbimV-gS-E8h", "1uUa9686MUjUu51x1bnbjbC88xp5_QHz0", "1Ge_QdyJJlcsa4c8Qh5ec9-zOFoXrj5m7", "1w47TzjJLj8oWFpk3tymhAS3hsDdNbWui",
    "1Onm8O2YdAlrQfiDOHDcUyChBYcU9kpTg", "1jkosZ79qoBiWZcqaONhhaxFFGJU3SceE", "1IH50-COk9REIVRjRXux5cttLSAf747SV", "1hHOS75XJocAylfy1rJoWp2aYR2X42yq3",
    "1VdSX1uCp4jDnV-RmX8RIV9ac4XkTjI7G", "1rIbbISMGUTde-mW6TLk4sZf-MTXlFKt_", "1_UxWb84Ub43o25G9pMxygUsExagdjR-y", "1_8qt9gyC3zIlPy5kHrk_RfZxrmbhqzSN",
    "1nP3Y5-a8AP2qwE7kUIBejNHbSwBjb-a6", "1hrnOP3x6gnb1_oQ2Bq38gzji8nlBWcyp", "1HKXm5sffav1M8dxJB7ihJwRWF-kvzhNF", "1vX8qg1raINkomZYfsS2MvPUPlrsqBvws",
    "1dIrjq8bNneEwmsqVbyv9uOl4KEdnoMw_", "1bDAB-KO3bvop_4hDzmIbuPlbjZ_JOFop", "1e13oiZQNjXyqajiuiVCtxXqRSfqDR1-D", "1A2wQ7RGZurmYo4EnwzhmdTChmTvmi8_1",
    "17jtdEVf-pgEe2UiwFEvmF8m5b0FZZSEq", "1rl1E_VF6rBLwcWfBYJ35cj5yk4K7_G50", "1UWc4M6TbxlUPg8_7Arl_pC2OogQM1yX_", "1zCuCwGKPaUNQE4JOvmKmjWkWwwxp4iTj",
    "1dcCN-cq8EQLVGODYFPIvroiz_9JGdSr4", "1j3frlXZuPNHpG9Rh_wY9viQhSau8YEz9", "1lKmLhNNW4SVOOQgV4FEa8oRLlBvdJOPA", "1OkPg0SHgD4yGYtWRkzbf9GkEgXHZpPEs",
    "1R2ZjSjNfbpIRgm5SwcPPYhEn6dR_a1Ro", "1WQ2P0JHmi8julbJHfjDLnz1xT7CAOlFF", "1Et8tLe5DuxSumBCCqiEloqEdsSUtRUYI", "1lTb8sGEO2xzUaFjrhJeWEOT1EbAtK4q0",
    "1c7iRdEH-yHcD0TNMmdbw0PDtGmp1LBw7", "1IF_P-wTqEg9oxTbQRW1kCLeR6jVoTszq", "1uRK_ku-3HOE5fqrGDRLHrYCz6dLelK-z", "1JDEnQehfVfU8HlUNAALKjwVWLmoCbniP",
    "1Ec90dhKgZ3A1nUNmpeVmb18OjqWCz5LY", "1yT56ueZFQPZ4Z1143jjcWrN-EssEfy6w", "1WqO3RL3VaiM9aTBV5Sqm0lBigihgYXGj", "16DxWHt0lMZxQ_QHo6G14rOB08XBZ-UCY",
    "1_woCB2i8I_-G_SIgE20BHHXnSYaYIMcT", "1iccmfPHvrXe_sz4KAeeKrPjUV_QYEgvE", "1ZW-I9lPeY5sQZrLHgmPDFHapAcIrL_-i", "1FSzp45I2awm3GfnG8UNBy2Y6AcCc-M5C",
    "1OF-geEryMwlOvZusPkrTxyda6cEsU6wk", "1LkPC0E0nXZ30deQ1CsaeYg8dVw7TLARS", "1bR2dY5dpboaUwPSK3z-0bgviA8GkKklm", "1Fep7xF8dkozsrGC7nDxik3LtoTYGI4Rn",
    "1x0Gc623bvds9kOpZKsj_02gqlpdf9wrd", "1wHkdtmWrCMTR22yavOkOfapjWO9_A5bn", "1eLof9pNWATW_-2DV3vrljZqTh9w9Rbsg", "1kwbefywtP9mYRKqGPB850sNptdWxwwmn",
    "1gqZXM16JibZ2gyPG5qS0tKLhCaJD3hVu", "1rRLk5yHy-KsbS34PTYCx_k1Ivm3yYaRh", "1weWLZJsIlTl0fpSFDKp2oCPjCLhixI9a", "18wjOFqfdf6D5kQ76XauhQ81SrsNc3Un3",
    "1CJ-QFb7dLxlZVrhO6GdtPTYsk0rmHfKF", "1vARe9VMAHMz1dKsQil5TignBZbR3lf1U", "1uUHKFJ9Z7hUGOK4aQ4wXnDvaALvbLijC", "1uUHKFJ9Z7hUGOK4aQ4wXnDvaALvbLijC",
    "18EvjszRolJWiK6MYbQcJraVXNBTjkawz", "1Mski4ka76T1KWqA4NaYDjLRlgFcrna6n", "1mQA0UvGrEsiYljGAQIPch4wBM16wS3tG", "1XB4CL3OTjzv-jpYqrNRvUd4sMBnUphUt",
    "1zlwJpug6ZR4nkVKMIzNdhePCd0owjvxU", "163xGZOEPmDeQZdm4npC4Txs5Yib8BwHP", "1-wOCyQIQ_PUVougJViCHzIlIq_tbGVqg", "1AH7Ux2Hh74dBVNYaXjDjR9oyRzHH7svP",
    "11ckjKb9NVgWz---39O0mTHxDRNsTq0fa", "1wf0zvG54kWJ_KN9nWel9zXxWgT2l8yrz", "14vKr5Bo2xBF6t6qOofj06uXVSKJGGoAL", "1jbky0JhLn9ff5Y_XIjUdZwH_e9bgylKs",
    "1g-O8ONzgWODJME5p0rfOuX4SLLqYhdhZ", "1Hhtunh1bUZRSpAL8d0lKfvx6YBqPFfS0", "19PXh8gFAb8-cNZ2uwxMlBObLmtO-B9mo", "1uUio9zk4fGc-IuYUzpoaAVMFgSVTfc7Y",
    "1uUio9zk4fGc-IuYUzpoaAVMFgSVTfc7Y", "1T___3B8t-gCRMxAV4VyUkBwDH_k9sxrW", "1Oh55-_L2wQGtblA6dcK_4i42gkAkVVcx", "1v_LGYwg28ZCRmaVOxapH8Qje7pAO4Arg",
    "1GHcsAid7uBo9cmSM_KLN9UgsGQAqYNmG", "10di52L9X06hsm_tHEhqKspniXwAWhtJS", "1L-5LlCaoZ16h55F7F43TGUoiHyRfr8U8", "10SCEKSnvwRDV_NligzPGtExS8kYEiaBL",
    "1AIMwLPslKltuKpgDPMxMIxOIQFS6Eqa2", "1e1WbRn_XMm21hpsjyy1yU2NUkMptj1lF", "1TNY8N2CuwsUeuHew8CU_ua6Ho_ckEpv2", "1hR4LstPkojSGppgAhmt-r3uVQt-_O9P2",
    "163ffvyHc-uB9dMPvDva1_ClanNo1fPk3", "1sN5KvNKJEmmXAeQtV2WKvWse183YYLuQ", "1fml4QSO3iwOK4ORkvB7cnJhKsDlxxFiV", "1RRKOeFuejh6FRE0MVqrw2w0f7OfUD-rM",
    "1xYmZ-kJBjHSKRgYydV2EzbaBj9_VL9B_", "1JkuetHJ9yWIx4YBm8LYzojqk4hQSdkPJ", "1qwbXNbq9ptKsHinS8rdaKjAB5n2hgf3D", "1tbNr0sPWsvlv0V7GxSbrLtqNAoXkkhlC",
    "1jwMHFU1XooIaKS8ooz-7bw-ci-VRWyC8", "1sS039DPzf6uCWkfDB3GdSjydG8u3fumh", "1miKFiJt4rP1j1Hkg4ncrLCT2DTmhevDh", "1nKn0_rPCFc9GXcAbEfidlOuSk_VeDq_h",
    "11JgoA6zrX-2-CRDD4MOuYP_-ftM-KZbu", "1pnj6bWRmfMOHDe4vF84eFc14otpdCItr", "1QztHvB7uMfVmgBKi9a7U54MCcVQhEnAd", "1Axpx1xKYIbFkIWElEy0ac09K2A_J-Nin",
    "13hC5aKMEv9ULNFNj4dGNoFkL808q8a-G", "1l8uGYOqfcznDbmFnz-jISsApdlQotHTX", "1NWg4BDYLf2NtJVNRvTy1l6AMODXqmoVi", "1fQaEGElxsKMTVAUP5pAEUiuwfdsy4-er",
    "1FRp7rLODrVEhxGL2z6Mc_-K5-ZB4l0Lb", "1MksNi1TLKfh5kRrVI87pwenu7hpW2Mnz", "177oyVzvL-epz3lBs0lkBUA5kZq2dD9lS", "1k04vIVpqojlRcMSzpJu1kTWQRT2MkxHe",
    "10Fg1Lx7OK0bZ8Yc14d5YfzoAcLIo126h", "1-6WeKYyROwV3sQJDTtA_eegfLw_XsM3F", "1m1rm0f_gKKGd_czlw9MwuJx78zT5P3CK", "1HNHG8a3A59W4PluA7ZssF5SJKa82adgo",
    "1ZfDBQgxYEFrKgZkYAvDsSHEmVCNuGlvK", "14cZKPFPz7F5Ocjzg_q3s3KjclRclXBbG", "1WfYfx98vhcvzYBbdEWSOCBHeY1bR0Dg0", "1EQ6-XC5CoMZTomD_1od-e3dDl8a4ZaZy",
    "13CnGqAxjxKZlIhtfft_TXegW-yYzYPnU", "1A852mRvrTmIFs4D4ZkqordpukW_g4CHJ", "1DvCD46jvNRkHO5azGrKpy9JHsFdG9Ard", "1vj06l5GoKfWwEdYlrU5JiHg9H35mMpBU",
    "1AYJBAXvOj9lhh6WqMWr-V7qVFYH8h5zQ", "1-BPFBFrW7tF5rq2EVNBhtmMh5hfyW3vU", "1LLpyYWH7pB_sHygzjSbjq-ufprGO6PWa", "1cKG9C-masrIpbQmP7Z9u_QYWXBGAHYyf",
    "1jCL3ohmVxXZ9rMiRqafD24GpzzWu6p5a", "1Ba2UmA9FNl-sYNVAoJqnkKq0StRVF9fp", "1gI01G8vG5KwVUqUVZOO4uQ5juFTzi4NA", "182eqX2FofFgPNitlolMhzCcDc4zBN412",
    "112yGfhChfb-fwVakPIhDjpoRowy_GSW9", "1oo8XjFHboWwrFRcQ-q9qK6e9OUtZkR2s", "1lVWxy9kZs96M6tkrOeNmw_qD2KEFj2kH", "1HNRj8D39ZqK1wr0hKE9-S0aE4pZUQztP",
    "14kItrOxBVC76xqkW3l5klOlmAEZMWovi", "1mebDuMExI5pL-9uyHJTgoowcLTsO6VM_", "13tUvdVh-FXGwt5K9xUx8OtKyj9HP6jO2", "18aFgePmYvYXvI0W-BUW75-J29glm8WDT",
    "17FwlimGWYEnqkrClJrlY2GVZ4-h0BYKs", "1L-ktoQP2lPJ2_fcoYPKRi0tzzks4S-7B", "1IM8syjJQYVv3Enrk42UwTkDDVbN3B0_g", "1gfxwITEekm3Yy3B2DLGJrFEy1g9qIzcL",
    "12Gaf1V4-ZsYdrZiYshD8tlMAW8E80aO_", "1dvDEwGue9oNzwL-cKSwOujXuzwvmmSnw", "1MBqLY1Gm8EMgkso-SW3YnFzWrQFdImLh", "1dZHzfj77HuRQnD3h6bdKhdyWbTn1t1nM",
    "12NWb8jp3kXnijqV9NPxYVQ0AgiZRPT2k", "1rz463HfsTlo9huGWCmoyIGzXrGJm8CoP", "1JItUFkvOUkcOug779dXRvI6Is0oN6gJT", "1Z6Q9PBcHO2X1Fo61StWdQpWP5dlbEYKn",
    "1u-HCw_oq9StmW8wjpBCdqZAz64B0-BBD", "1ATC4OTuuQTuSnScNSpSdqQr8s2w3PR0j", "1d8uuVJgXbfhrzdeWQs0Y6GBa534yY3FV", "1KgoR-ogZa7USujDzXw8b_JchtJ0EuTzV",
    "1AR5kRIQi5OHYVpIR-oaBF25lXcy8fqHC", "1vTRbV7g5qj3DEkakIy7kqRCCJMbE2jMV", "1Sz19Coo8rSnbLod28SVOQuXCZsCuiqmI", "1jWRAF1to0Oa3FRkC2Fee3cw2oLLHA_gr",
    "1SFtB42W1gvolg233wu_ov6EESiMrnQoz", "1TcGgHbAOtub79TEbXEMI2egFQ8eckmuT", "1RrJ2MEFtrJFRrhKIJUCVIZVTqIB0fmNC", "1vdAnk6lQXp401vXg4JqMz5qaOMba4BsU",
    "1pacN8k8M4H-HFmj0C2Fi903ztM93xQj9", "1wToSTK-ZFnbOqcbdPHg8Wtuh1Sbd7YwR", "1MGMBEbI-V6Vl68aSxKdvYAp9V2uWGHmR", "1Q6k0w5YymK52Ke8ClqcOEtSfm_OrnSsx",
    "19IVjohoAGF8rWRuk-qINGVK0X6eT-HbC", "197MOPErI6NNgraEMYF8JBS6Qbh539B7d", "1kFKkI_mD6CJ_LJb2yyelKhGbf84wbKDJ", "12fr9a4pGmHM5eKkjAuBVhy7q4aU5LNEH",
    "14eD2t82pAGYO7XO6sgAc1n6wn_ELxxzz", "1VUuPitgr1FK-dNUd0pQ-3ehp3u8fJGI2", "1q1JR9Cz17A5GIexzDv3UVUo9kJ02QFSI", "1tU1L0UgVCdv4MNq1VY-QmhDrqptCQE5I",
    "1ie9Gvm6bez15P-mLRLzBzV8rXvkoIMio", "1lGKBA-WQRoxCSOZWmudxH5Q6G8YO6B73", "1zszUlIej92ZTPJ9MUoiW1Y4S9CseUn4t", "1SzOiuLOUG_gUuV-Mn71qBq9YrbBjUP4E",
    "1PDFDLp_KockVwkGQ9ml_VVRux7S1WH0p", "1GOzjXGvjfXaOsi-Z2NDs8UBtv9D8L8V5", "1yhyOSap9UytBEUX_X8Sh0X-K6V18Ln2C", "1UavIaGMwEySqxMKwuD3j-2hE_nh3jw0B",
    "11fseUxXm-vGZncRpuq5Zy4W-ri1rBHBD", "15txIjQPS0Mvy87Bputdf1eVmZxNph45r", "111MYIfmeKbb5OEstsBAvZPjCHt9WpzAt", "1pwpm4hyRMBkPgpDQHm3nNQS0cJk7K9qV",
    "1_MRzyd97_1R-tBbQfcPn0KgqTK2zGQH6", "1pidEufdswTkAfkfKOIXRqqqOdREm-JsF", "1WyiK5jKcRzsr6burREEN2usFQnPesOwu", "1B7JnkmIAL0KlXxUQnGoVrex9yurvz-Ee",
    "1VUxmoCkmX3elrYFEKzEPxuksyRp75zHS", "1tjKKul6xIl6mVh8UtzNkKF7a2cXaHj-Y", "1iQ1HrGzxD5fucGcqqtfGOQ4MsZC2Nykg", "1aKVxhULS9ESM9YrTuvHY0uugYBoU-EG7",
    "1CCR27pTKsbnp5isN9Zs4_aCaW2QAsFwc", "1l2zxZJG_JSrabcjLDkNiQDUwLxWQePGw", "18XV4mrXjw7VXhQXQTUiHT9axy855SXMS", "1rekWGwY22Wjshb78nxUU-5whRKllfPhn",
    "1q7RuR5Czo3oNR3eucI7DS9VrCE6HzkKR", "1ZaX7i1NdWlY_3d-OgcG-_HTvD940Nrk3", "14PT0lDXxgcfCVAyCasIpWXvMpXNxy3Uy", "1q0Dmmd33MGNipLharBwkgnZp0fU0kFuH",
    "1CQFsp_PoA7lUn4hfTCJu_sZFmC1ySHM8", "QM_r01EpoZHpVyGHoxQpDBTDYuDnjNJR", "1esNo5wAv_nVrPfWSiXPjMIuvfSUGfI64", "1TsexDQQioXQ5-scxcsFYgu_JzcJimPXi",
    "1NpUzKXebvMdQE4Y6E5JRxEUCswQ3EKBR", "142zip-DGoVhjF_qjQGAXiFslrNo13Prd", "1DzOVQ_U0xpp07e0BFzwBxFq3Q53lK-ap", "1bHZ2OhizxOVWMdXSNgsAznjo-iYhuJck",
    "1gYiXT55I5oa7sUiggwJ5qQR7MDinb-zP", "1FPZlZlYws7J9yJG673q-mBmZpwG09kWV", "10eqx7t7U_w4rGR8vhvR_5QOEDTXkCvIP", "1talqvR1I-qDO9aVFfD9AAS0xaZ0NB5Sw",
    "14zmzII1py1ut_SmKaMpBNcwrsXP0VQmp", "1_LYi-B8CD7WiBI2UgJkjNTttaQl1_fFN", "1UAu36rqkXrU529Jekz4Q3MxYcLvMOTIO", "1fk-U2tZmxJ89CQAP66AvcIMxJoyw9nYw",
    "1SO8Qmv6M93KiR6yuUwUu-rWNRpDGJLqU", "1n0XU0m3Gfd10Lwkwd4jiPr2TP3EE3-Iu", "1_2V3ugqN17fCttSXNbtITcXTuEO5eIvP", "1YHdFMiGLbxMF-A5SD7tWHIsfljm3IlK0",
    "1u8IsLO7pKdzaCveRB48fZmwu4GPjJLxd", "1TOn6sATcCvtVZ3iWhH0BtWIWxTqap134", "121HIolL8SL-3Gsn6Me4JkKH6wVqhgIGw", "1ezbf2OrwZUohmR11pdxSPfFH27kZDGZC",
    "1TAEh2bJDxXioSvu7iLKBtIgIUbsnLdaz", "1is1cGL08teG20Nu-b-vwV9aSX_shi_BM", "1eKd2qhqaPe2veYcgwzQVbV2UrShYdw3v", "1D3SIVf_TB3i2bsR1_nLQTcSPwvhpVlkJ",
    "1p7xwXjG1Zt94mqFAVBsyxoOdVovkRecX", "1hMG_xgHSHJ0opI-LAWmFv_ZeGAxWNp_s", "1QaPTyScBRWN-qiAK1BJmYoTZF76Pe4ev", "1_hUb0fktAUdRKVyWFWntW1IcdPW5HUcP",
    "1blZmUNv-S5u14aS0Kx09Xigvqf0gKESf", "1YCcbSbNPK9pQXOBvBLqJbxhnc39cmmdA", "19DFV7jYn-jfjtLI91bF1HaW5GaZtZJKc", "1v3L5H9NdR3w0QG3OaVzzQBeKglPs4l21",
    "15TU9BbNSh-uKZ3LL6UcLwZyK8m59hYqt", "1e3_1NQFvHx0ZmT76KejCcko4xQD3uXXf", "1iXc1o6VZ2dQH9LNe9us4BtP3Vkpzb6LT", "1fRkq1Tx9x6RxY8l_sFS_PL8IorNxuUa-",
    "1AQhQTwO7OpFeNtA0x7oQbS-V6yL8il5I", "1wYE5d2jiZJakWAYm5ysuE0_gi1o9yW9Y", "1JYKztLRYCGGiYBSKCmXl5ooUmK0xx8XS", "1vSywM1msKr5mlWn7fIADSQSCcfbAY04J",
    "1V2-c1aMCxB147Z7HOabvcHk6Q21aNph_", "1Z_HuNbSyQ7E8ltcYtLdAQwlU1xFm9ZIH", "1ALJTJUygRNhBFwI8X-NegjFrSmVAkjxs", "1ni6If8urriujfE898NjhATPCI3mhIKnT",
    "1ZoWA9qLOhr8gjxJUdRmyx5UtfwltqqsR", "1zQnfvm73s5ncBVgKLU84__aAlYO1bfxp", "1DuIWVWVe6nR1ZzDhuOOL6rnfh0Ef3qSL", "1ntp1hDa52eTWrMZZMQZMo63Vpw5PdKE2",
    "1MvHVKv9KTFBIRo_ipLrZTwgWRoi3a8rj", "1EPiCeM5qP1-yxAKZH41cOhB5pQ_UgkF0", "18SkMChuI1YjxRMwWZX_3a7b5juOyXunB", "1QeyOYmyAtect_MbEpYes5mgM0wStTsL1",
    "1Akgn8J9vj0tn3zeOj52sa_wb4XZbDZy4", "16SP8jdnayMEQJOVx7VKyz7MacnpO3BIG", "1NMQ9jv8_4q-X1De81H7L4k0lBRCyHory", "1tNZATm_VjQ8-bb3zdBbsb1B9e0lqWL0L",
    "1hwwJCqVyw7JhV7LlZJ8UuOY0RJmFpJF8", "1id1EpGL9b8V7YWfa4I_rLTNPJ87PglRI", "1xl_XD3ynvfULkUag9Nf9ou842Kg27-xi", "1pwxG384ExFRm5Rl6Q_TVIbVyNGD8YEsr",
    "15eke0Fn0FDYdxMCIwKDZOwJzXC8yweFC", "1rNXKEPTp8JBwzsqqTwwjcmyTM_CExYak", "1GpaGn0nOYSnlzX8VihInnD8YoJQWtbVr", "1HpyzAa-dQyFPw-ahru5vA0i1VA60oI7C",
    "14NxWTajCvHE1xQ5KhoVNgskc-NMB0OU2", "19MjrHjICj4wkLtnTVEcXfuaqUAcr-zdD", "1LTWTK86AD7abz72v6OrO1qFgbQTjV_Ce", "1nPK0W0rlvSY7kj34sr51rI3qOCyibVh3",
    "1fspDGq89QHicybnOo_0xz3BmlPPHyUv2", "1H99PVxZBa-MHl1WN2jDf8FyaZ1VfyfQA", "1SDaSKRwDM2ijw1PrjJWvqR9H7CJ_k2wV", "1jpHTHq8rUJDKk31ipWTKQmq3hOyalPWn",
    "1BCmKtSrXCMHLA0HK-J3w4hF6jPSwPU1J", "1P7BT4uLoR08hRuyWqlAYWB5tM2iNTzPh", "1qIVttdseVwrvcJVFNeqpOUS19X0RFk7e", "1Ec8B0ClVNEAY8ChluCtnsbgn3XcHy8Pt",
    "1VljEurU3Krdtf9NjSoNO84D-cteb3H6k", "16GzOdpY1cROiKadupXBlYHcJ1ZwHdcPl", "1xbYqKg86xiSIsieA6FMQPff5ZqlHdQOD", "12MuB1AgRKi2LLREue2qWZ5gIfSn0iPA4",
    "1siFnWsuOa-DbSMytA86gyPH0Gk5S42xo", "1TVjFbJvNhqHchmZl56KPF8n0QzIROtyh", "1RsB01vQU46QKVt4jp2z1IhFna12zsNfV", "1VNaJfzAt4uAm5E-lKTCMuFJn8id7-24T",
    "1n70IHtHztdUa6ZfQ7blj_q8pRhubv75f", "1xtKWHI_hlKuKl3kG7XrjNEXpdVVOat_h", "11nS9qsd68_2B6ftFW3n59BIJOYU6btuw", "1pqOSZnrK_3bVwt4HF2GUxIrihxQZQnFb",
    "1Tc488n0QM8ZjKQ-Xzn038Mj0rJuiEllm", "1c7zzfLF9OoXe6vwgcaYWU19MxxMbQp98", "1CV_qdjWnez_ZAv1sz-o7l7BsBVkvu8_1", "1SOaw2Z8geeW3PAjVCVmiXDsqnOyteceE",
    "1yo01wIXw9GR6M_y6XE10RSsD80r2wGbP", "1rEoUev1dHLZFUofk-kenOdIGyYvr-puP", "1E0Y0HQhwqTQnVLAM2-07dJac2v9Vc0nX", "1TTI15pmRs4hdUewX3B1SfCMxxfODk85f",
    "1fV2uecR9qNmD2v8fBQqnXxqC6LFjNZeP", "s1drTb9_8j9kY9PzPr5TVrKcrEFDTbcX", "1UP_HiYIzicQr1P-YMkxOR5M5FTHW8MS7", "1WlT_o1TurJUk9p4I2nr_GzDQjgPkoAKi",
    "1gAhoieWkPnZ5JvsR8kSrWtyswA2-5YH2", "1JeYO4o112vtwa-ebE4pZhDrQ6V8Pm_9r", "1_lKaml8pk83NFicZ-kizvgaRNDgZkvrK", "1TwgYPkVsPqQqmoc3MNTBwVhix13qzYwD",
    "1lvWHUaMpXasnZrH6xgB9SgHHxw80u3Yg", "14eUSMJjHWNPRhNQ2YNBT1gj3mHTTg6nQ", "1AuU5HDo-o9ypjl_xUap9ViJPRkpM5gUX", "1QnM0vcPTdbLWZjFFrnFkSWvXpFKtAT37",
    "1khgUhpyy7cbzzoVyMkXW3CmHSuGeUxcp", "1dqfCvmHB17ee3dtk_7nJhuFkPVQs4_MQ", "1sFaJjuGy6eiGSDWL04j1F5K6XEWhM_82", "1szJhlnEgMGP_ZLCPkiTHA3XwCH05KXDB",
    "1D7ui_1oPGZVrdTeIWaQ3DtCMRit2PPVx", "1-P55_GSgs4o--0YtIPp9Bj-fQNbYxr6X", "11Wa0zpVnySrCLbjioV8tsDx8cTPAbv2H", "1a0DHjJSyOxqbP04ngs40Uby3jl2T9qVb",
    "1lGbTrIzvynatutu1g_dQzeflXcvTBCGs", "1pPt6Q_uJPNFUJxJ7HJlsMTDl5M_zNpej", "1W0ZiylcD7xhIMKUCJ_opsYf7X0EhR1C3", "1GHZ6NhRNbc66QlBnMr_3y0jzmj1rZcGW",
    "1q6ve7tVl-GyE_flTm7b1baZzZp2ywo4X", "1GN0aIXh7kSYq7W1jUwaCEuvT3IT4x-05", "1QumvyFdTjF1ofguTkhxy9hP8XuuIbE15", "1EGak4G3MydGID64XuzHqrzFM85D7BmbE",
    "1PsA9KcK45L3GnENE6J2zNy3-OZe_07nr", "1ZWUt10Zv5ndvieopG5L_q_4BcM-6blD6", "1Y2ZgBHPLhajwv8onoW2AyUFfwtuAOOyO", "1MjC-WRDIlHqaTSBvIwZQrOl2oxJXFTnA",
    "1R080V9VUHvsQxg9prVvnjjXIKBUZrrfi", "1zHUEwOe2vAONYpKxACcVMrj-uvFTJane", "1xhKqraueautKdt4Yl1uKkhKVDHr63d84", "1VIMYlGfzg2q5twAehZTU6WmXVC7E1dLN",
    "1ZGaJ7fXFnyJ9WDiaHk1kcKqkgcMOMIrX", "1bBH4zngBOLc8D0F3MNZM7JkDYDAkZX4E", "1ZYfTKxLoO39RgFvlJ8I59X6rEwhgEHMI", "14SJIVUrLgm46TzJOXJnw44q926OJCl_A",
    "1TyN9ezh1x5p-wq9BIuw5ImVpeYTK6HLJ", "14fNj-YS51J9stSHhTj1OnUiFe0H-SCaM", "1dXZtoFbA5bvsZd9TRDaSqRLNPhjYJgJd", "1-IB1pRqRqaVtHgJey9MVQXsULhUxbEF9",
    "1UK0FgmnsQF1WYF1oBOERbXt2rc1npuSa", "1GtmCg2lvvcXcA8IbMQzpO9pBlCbJh77S", "1VUcEdqth2Qh0AZ5VkQke4tNW3Qnw5zDN", "1XcSiqVAls9ZyoH7f4QNs1z6gbV9y0QaA",
    "1uwSgJiABS3E-mNUdUCc3hcAB4ZwgLDRK", "1yf-6QuKVIFwXj4CEVPMV6yS8QtaKzzcL", "1TjJLqST6GHJk2mQKgB5j_I3HCOQ3R1_Y", "1fIPa70Q5Lijqtb-9o-WuVRT0uMYnheh4",
    "15OR8BClvMvwF0g-3LdqI9IOOEomn6Daf", "1FK7SxbrROXDW2fdxqOXAeCKG7-G3dW4z", "18V28yMgDkikYOwAfVtwiUicpdxKPDAL_", "1-B716g-aff2zTEpbj2H5RJ92EWYMULO2",
    "1ZlkmDaQjatS2oTWBZpf55VOIXol9GvY8", "1cx41rmT_rhHHxF804yfwDSGkbS3KHTnW", "10ecl5S-i-nFs5AlM8YVPwrgH9zv9YC8m", "18BrC40pC1fUQhcRm7MHYUj24vLPaKurq",
    "1XKTipGG2wqC43JQ_2afmVIb-crNNYVlp", "1ehss3xk94POQwccI_H6tEeoC-zcQSBpJ", "15Fw7DvkTKkPCVF59NSDdbbgQ3P4K17WN", "196y6E5yjOg396zpJSe3rpZjyNts_Mtre",
    "1vFF8zzhV-ltgsATC3fJ9Ey0c1wyyyTo8", "1fp1xv1QhU6pXfeThEIqtitiT6qDRMbNv", "1GTL6mQzkm3rRt0yOmMIWPJafb5LgltUy", "1GTL6mQzkm3rRt0yOmMIWPJafb5LgltUy",
    "1Ei8wZA5buo8leSQ7FF5hoMMo2Kzm-SwS", "1YIXv2p-huGZbK0s7pbXhQou3Emk4ZjvG", "15elc_BzoPig82dajuhS9nIz8HybiG66G", "1W-5yTl8Zy-WM2yw0IydxFN1wiOu89_XY",
    "1eEH3e4NvThZbdD8vhAHsVNuV3t5YWVdL", "1KBW4ULU8IU-5ylrX0MjMKpRiBQKRIe3p", "1uwZoX9WfDPJqhLuJzSEAoOsXtjFtnUiT", "1_gOKCjQcJcsy508h4BWUJn5swaQKzsAT",
    "1tKys9Oa5Y-KQC-vzrOR6tGJWORQ5S3BU", "1BohDFZUr2Q-dsUDztuj8yIr2ZCwAac3D", "1WKYRo4CNieIatkEmU5IY21IAsVKZPuxJ", "1Ph03X_1JMkWHCu3BQlvo57BxHKHKcuxX",
    "1uWvt8qMibvni3Q3lSy7cGoA319551QCk", "1o5F8xDfdTQ39yM-YNOybJelHhzBby8RM", "1cnF-ni4N2Qc8jHt1n67ZhEP_3_m0kdGl", "1C4UdqzhAb-keoj0BeeaTUips7gA0xmCU",
    "1MojjUX2ifv2xQ9P4RxJ3w1IE67RKdCGq", "1iSke18L_U24tz2-yMfxf13jxANni6pUz", "1Vitd-mRAiyQJTyYWNRcXsKCGS1To1WwW", "1P6jT-jO9xvMaxN3Yw2Rqp0PmRTghYUgn",
    "1uoLKElFNLASTr5zVeoRH5_r3F7XGtSzv", "1DDGTehhUclOJ-9VmHlDlNm837mSFIsly", "1VT5uybQu8YIbn6WKjDaO7hr6s2zuTsol", "1h9UWkhHaWlIJKMMQQ5rfptYSlvlgMlLz",
    "19q1NQ4XoS_ptY9mUo7XRZwvEnV_MOroX", "1-od4Jx3Ks3D8xMZCooozKi7OtrxeBEvU", "15_L0PZ8WBzWWB7Q47yl9Etuv3qaeU8Gz", "1uLGM8Gw0N3PWruHZMc2Ly1Ehe0gPlnub",
    "18qtNRuSj9Zqleo4y-xL3q-xoVSWubnV_", "16qjXqcUnvcSsGqBq6lLAvWSlngV8AJmi", "1zeDnB08rKLLPPsBr8-BoTGnuQeRUAB3J", "1AEkMCNaQYexoKdbCh0nUKh_yhkRW0omy",
    "1IBvDfc701d3W3FVPhNYMMhY6ijCH3Ct4", "1a1Xy30dVC_-BOxd8R_8gqOvzBhBNjCYQ", "1iQWLmxhoQDxLJQ0qC3BPMzlNYbGNZRpz", "1jUAPcTxW56E-Tf-2FBNU6q5xWK29kunI",
    "1r6ePIq8PzRdqvejp5QoBni2ZNlWV7vb2", "1GhwVOrMcNpFpGmTRMD2zFle3Sk6WxQp4", "1xnx7RUoEECp1EBgzaTluP_pdp9GivQnY", "18omH-kmaAtdh1gyI4UaGJLDsIRsWhuz7",
    "1SqdecYT5Snwq-0jTP5kJ3FTemgsTd6js", "1F_WZPoWMZLAqWe5Ahk7M_6JdQXKQX9dJ", "1yW5eGaHOnLpYhGA2ycGcOgRPWpyKqv4z", "1uTVuh-uyYv-jgqkvh-YVSkZ0evm6Mo_s",
    "1gS3Yd1maRTsgEp3KYH_PXbsFRBbTsy41", "1pwPg1HS8odxon7WcNcDCZGF09prCPVcN", "1hAL4il1BIYL1yWCHwpm_TUWP2GkPNTsa", "174YVpbQM2KVL_8LphOEQo2YS8-j2blnd",
    "1kMvVfMHDjNHaY7_Clb5Rv587613vUDsK", "10jbXEluVwRv5R9hsOE_HwXSTV02CeAkT", "1zwcC6IBi9MmUnbGpUq1tBsuev2WpNwvc", "1W_7BDjpVcTAch2UyL9-hhELMsxUWK-j_",
    "12C1-KuDkY3dUymcTtIK7KaBlQ9rDzAIh", "1cL3YYYm3t39rxCO6VTJioBdCNtg85Owz", "1exwL3ntNYvqW_ZNWgIVJDmBeZqLZkwfM", "188Yry1Z1pYM559TGLua_oe1iSgY71nwT",
    "1QjPYnqtW-lify_ahU20FZFALPTUxdAmt", "1Hgy99Khb8t2sxkJGUbA6oeArsM_f8oWF", "1tDD0xUyGD4M8pP10HA8kAaTlPel397Me", "1YjlOfbF_kGfftXVyFZahPhvOqQgbRyN9",
    "1t1axnGMrO_hWdMR4yet1X_aGyn8qwFu7", "1_wonLj78FVm8dntsu-bw_EdOBKFLxrKt", "1ta7R8yzsSdxfZKfOohINhWM76ywxg3qD", "166WvKpLj1kEvsyDYAXR_xV9s_rnkeo12",
    "16R9lTXHHMASm09fYVmAx0_LwekF0jStQ", "1BX5FVaAb0qa3NyrtD7zY5LWBktb7DZTW", "1wD3m9hZvK4uFv7FmbHVv1iiNBosW_3k7", "1IDybcUJjeMXeHsBYQmOIGzf-t7-4o7Vd",
    "1dRcX3mKiOgsyxhp7NLqzwL1r2ykejk_Q", "1A9z0f-AJaAzokZKgv2N8dHRwKE9IHYCI", "1TJAWBmLKNBhN_0WJimWOW-y_8doODnbT", "10pJvLNLFjKq__Q-BrzJ7kAYxJflbbWsE",
    "1c-DuOxTmZVGss6XX9byFZLns9bq7Bi6I", "1dFAu6ZqUKMdo4Dzr4474HB6MZaCMHRYs", "1jUNDA_b0QOBSCM_29IdQPfPw8DqOQjDc", "1_0MxsrqY1pFg7vxaphWGg9SADObceW0A",
    "18hevp8987Gw1gqp6WVKV7xpfEWFaP62a", "1Ztq2HzCwgFS07frVXpCC4kfBXMn5Mj35", "1CH9KslRHVYrWIkeNXcBLEXWtVkET38OT", "1Z1BTICa_j1mHWOmslZVj7K-lfG9qwyii",
    "1lkfGFYXDD5kd-TIlZ9azguSj0itS1O21", "1BzXR4aOjR-tQwPEznwLJSI1kJBfhU5H0", "1sqd2HW33CUQPhLV-isDkJRO9DWBMGfwG", "1GK1bVvAEW5vyUBlQWenWRUJXN3XEK4V9",
    "1SqGD2g0sckJ27pHSujB4TMkTfd8t22hd", "1lei0oTNCcPfGfKEvg9tvn97lFBGQXiyS", "1Y9R3jt5-u0pPUTiHzqs4hzsTdyh09hR9", "1eea3Qhp7BKIpwHeVIw6YiSUjBKSw85lC",
    "1-g8w6oDtjJDfJ2E_BD7T08Qu-6sHoVvV", "1x2MctMtSi1uDN_8tECxcYvhlJUfzpF6g", "1BQCnTcCaqLAKj303BunMaanYbo1tU-yz", "1ix1GXyAgunhVoBnPOS7fP7u3VvV4CQsG",
    "10NEm95TnjOGcPhzXECCMFUB3uGltK_dY", "1k2me8P48pMLSAsFMrlV8jQFhb10wkU5U", "1MpxLm6HVP9oZ-6cEs0PrEd8KiAIa9_1E", "13m_WqM-2oS5csDD9bEcl9iOoPnHQ66zb",
    "19SZ3z-IrgsaQQJBzr0cgSA5c5x1JfBUq", "1HSkVTwmo1qIG5j-ytmoId5xW9bgaLv-o", "1i2zRVzSBJBLHKKO2wSfBg2dE25gU0lhB", "1BSi5u1upemxpaTXknHUe0mu0YKhMCgPz",
    "1HoH0eNoUoA2wXqF9Hj-pMZO_USNhO7Kg", "1SUerZxOXWo1PI68iEcs7cDmkmANiim-q", "1yq4i1aAYXfxKfYwYf7vn0D9Q0fZ2AECC", "1bv2C7OAEQ6SEdF53cPVooEob08mI3LJy",
    "1nYDgAK4KlAX9BHz60GqTM12J54isvlIp", "1hUP1rVZSAQ3xfNJbx0OnjoavYmNNkf6d", "1mM1MK7VFL_57Lk1IB-AYc9Fm2YAqU3ne", "1SM9yufzbNq98s9ghDv3-MbPJGbUn-CqU",
    "1h8A-4fpY8Qo_FnduLaSrIhr2c4QeCVkZ", "1cqBbz0up7xGWHSyRmD7oYP8NDaQ0eR7q", "1cqBbz0up7xGWHSyRmD7oYP8NDaQ0eR7q", "1CzSZEaF2u1Tfynd0epOdFOhXcyatSZYE",
    "1saqsav6DuYpuh8_NqFELy4IZyNTHZ16P", "1KPUV6ozQElfC2eKrFd2CzU9rI3rB7_Fq", "1R2df366R5ELXGoZvuOYZe92eTqWzRuH8", "1uFTp8qSER6DXywHv7tatpQEwcxMc15H1",
    "1bLsA66CZVCuoPWkU12esal4ugouGWlZm", "1pcYV1LGCRrZjW-YQfEcPqg9qTRfWlC_c", "1gaplYJ0TySSzi4rVxHTSBieH6Kt_HR9c", "1s-7skcFMSbFaW4wZfL7wNcY-Dl1_hbx8",
    "1qyjFbItsEIz-XS76Wl0yFpXpp9YxB3RY", "19T5NXtTliurAukVECUsfOjzKW_xU6yyB", "15PbGApscCdAcpdwOWoCGf4fuCdSH2JId", "1rF3qJFGwbVgSdIeOju-VjJfDbsEgJB5b",
    "1Ze9LLi4yrQz5VQ9xB1Gg52ngHd-3cLxb", "1r8GalI1UvxLupRJzqo3u99D9Q1qQ_xyL", "1CxILlsAblGKE0uUSx63XY0np5t8yTum3", "1qgQslArL7-h1VHUMV0SBHlAFOLvjjKN5",
    "1BjRN0877yWSJqjoBXo3QgJghmBcioNba", "1AdYTRSzMIyPwcabgS1V7eVuVHmGnrlK4", "1Ye8lQCz2dPZt0sk2yBVvOlNFJYOauJKk", "1iT7jHW87bIqSVUsrJ1UokiavBLRqMTwz",
    "1Sp82akSZ82Q8oWLn-uW7qbaxdr2DGezQ", "145vYICy-qr3JtZadIVL0R0L-70eE8jJS", "1GaSZaZ9CJmluK7ewHSs7hBIo_O_UVf9L", "1LfCJBDoJRH-WzrgeRh_XEzndcUMXZchH",
    "11wNsq2npPqAZJ7X6PsvgBs3k72MbG1U9", "11wVYK9WFj76cGZHn9gY8i9-6SUzN_bAI", "1t_hqf71qZDYHHhn_oiy_66YvBL_W0qOp", "1ix_r-NI5TZl58HtrgSVobXLEbHw2gK3y",
    "1iSCF7iu_goZDiFc1hom2RUfNiZSaAVdi", "1xFJdQs_ZVkqgRhv4xiLpa-FUK90GBay-", "1hr83jm3968s19VGhprWUwkdiZ_rFyW5z", "1mskFuoAsPAowH6OnG5s7BdG8apIkewz6",
    "1pHtHkAvoYtUrmCqv8kNUX_rgBGg8fChx", "19SCB1NhIMdJwoHbIpTEuLoSTkrcxkjbJ", "1VCA_hKaWeY8Sw9N_ldbmz0ed6HWhNRMA", "1t_hqf71qZDYHHhn_oiy_66YvBL_W0qOp",
    "1VCA_hKaWeY8Sw9N_ldbmz0ed6HWhNRMA", "1EP41HWjnxkGnpjC_Acb1dSUlNcTXZr-l", "1ZZ2aiysWe211oLPDVcGIERKn_9f3QcgB", "1v1dcivfXMyza368HkJiVx61MGt-O4M5V",
    "1dKXEw87TeM4XL5Tis-KXKwk2ueZkQiWi", "1niHCyPV7nvo4QqD34L2fe2MyRJrFFpSI", "1157Xcn_9N5Dt8z__ApYSXDhN9gDCR2Yr", "1bGWaSFwmkcs1pPUj6L6-nX68UHWg7iM8",
    "1hZVCQLUKUUHLvhR7JLLAuvX26KJkqNOA", "1DXxK55cvS1ONs-bWqMfig77vFyCSancr", "1jKomYJLG4m1VG877R_PL5J4UykK9RI1o", "1thSg2Hi11gROjsEqw8KZ65omso1mtK0m",
    "13voTpal7WWv7rL2gmPTDVt-VRdl4Lv8x", "12-u4A-5QE2VYq4AHzKOyMaVukoUmzo7X", "1wQRnH5kuWSQ1fLCYX9QUm-PrruIspOjq", "14yeO3_o6Q9wVxUcNnGIUNom984NSjiAg",
    "1YXyPYSFccJoapJGPcHRumQv8giS6KkHn", "1GBW2Fw_ARfy3O2EZZ_OUWcSYFR5DIHbg", "1W3anWGUqPFVqk_a3q-saHPq-aooJBMdc", "178ftBXUjSaPhz4fXCYhHBeSwqa4fc31-",
    "1rfe0qdzMS-K011SfnjauRBZ7MvL9M7lW", "16Kd67B5epvUodKIfWpoePjLDOjPHCf65", "1z1xYV2edYlH5bbQgZLUFvBAgYvvWPt2S", "1OyE_U-U3sIg4g0K8IDXcyIu5syh0Dlho",
    "1qs0e-cNJerDlTYpCUcrDdISR0ROxHfEX", "1mcYMq2npmgcyq0OnMX34fA3kNPfp9SIN", "1TgTUYIsKRfPKgesplEfE2EqJncAcuPK9", "1vARe9VMAHMz1dKsQil5TignBZbR3lf1U",
    # openclaw-* folders
    "1G8j8mPnnVLi46S9yPLtyD9jrcGmVUbmQ", "1D7pXHAJCdKaXuxTRHcXIJxhybEkplSwv", "1iieGDgDEYmegiLR_EOTbQj5VZQDw0IYu", "1N0QpqGJjSmxCudW9l_4l0hnqIDlzmAMc",
    "1TngzPil60r9LRAV-qkGd54wnRfKm9CPg", "1ULnfBZO2xn2QJuLVfpLlz6S42Vx3xNGU", "1zkMOaxug3bhRSBAQ2vQS1gfu03hEF5VG", "1CZ1wz06kYYc45uBGi0HnKYckumCc__z3",
    "1TIFOdLoJyizUd4fNotmjIFRnNbiKmMr5", "10kjYbNlJQpdP6-8yZO-SU_c_HKHIQXmm", "1dXc5EDCovjiJpd207EbBMKcmFhYA_LbL", "1Jjuymv_edZkL8KBXWzuubM8Qv4MaYe9R",
    "1w4TwnbtURewP18ooK324ULiZmda-S7QE", "1O7ZSYbbI6rspyLDQuFH8sbYNRImUA6Li", "1Sd6RM-sjs3rveoZnUb9yBn_Cd-8fAE67", "1cUnefELd1CueB9qTH7X7DQX1wdBdnPVA",
    "JoPufrZ1ZI5FUPt6SB5R7lt2rUD-qZyd", "1AUnKKynZR8cIPz1bttMwveox8bcizraO", "1UT3zoxaknvsYy3e98I3P05TeKw-E9_Z7", "1bl4cck38fotpyLJNDf2eMzYsMlbB55xO",
    "1P_GaA4vQpmouVWn5sfktzUbRaEgOcoEu", "1rzgpMMn8tqHOixElb6GKlAnLK2COwvl1", "1yCMzYXxzgzXTO2DsP2O_NiOuAOXPejrG", "1ZDpu0PPRGPV2dyaz2p8CPjqN7XH-RSeB",
    "1p6LE2rviO4_M3IVzZGETXYAy_A7-j3YF", "1SKbTLOow3vnvTggfGi-vOoIQQuV7FY4j", "1aK7bDu1Vod-ifU16hHhP6nDYR9L9xGcP", "1vkwr3EpXjbZkNl7Z6SuHSCfnSBK5VGup",
    "1sit1d3zTqGtE56GSq2Kbiq95uwAO5fc1", "1an9py0MdAvdSiM-nrb1LMZmV_CHbNVeZ",
    # openclaw and hermes root folders
    "1uBwL8OJ-XrXaBo4Uv9niZ_Qdx3JaqWHS",  # Hermes
    "1sS039DPzf6uCWkfDB3GdSjydG8u3fumh",  # hermes
    "1miKFiJt4rP1j1Hkg4ncrLCT2DTmhevDh",  # hermes
    "1nKn0_rPCFc9GXcAbEfidlOuSk_VeDq_h",  # hermes_cli
}

def get_drive():
    creds = Credentials.from_authorized_user_file(str(TOKEN_PATH))
    if creds.expired:
        from google.auth.transport.requests import Request
        creds.refresh(Request())
    return build('drive', 'v3', credentials=creds)

def get_scanned_folders():
    """Get set of folder IDs that have been scanned (from scans directory)."""
    scanned = set()
    for f in SCANS_DIR.glob('*.json'):
        try:
            with open(f) as fp:
                d = json.load(fp)
                scanned.add(d.get('folder_id'))
        except:
            pass
    return scanned

def main():
    print(f"Bower Deep Scan Resume (skipping Hermes/Openclaw)", flush=True)
    print(f"="*50, flush=True)
    
    # Get already scanned folders from scans directory
    scanned = get_scanned_folders()
    print(f"Already scanned: {len(scanned)} folders", flush=True)
    
    # Load folder index
    with open(FOLDER_INDEX) as f:
        index_data = json.load(f)
    
    all_folders = index_data.get('folders', [])
    total_folders = index_data.get('total_folders', len(all_folders))
    
    # Build list of unscanned folders, excluding Hermes/Openclaw
    unscanned = []
    skipped = 0
    for folder in all_folders:
        fid = folder.get('id')
        fname = folder.get('name', '')
        if fid in scanned:
            continue
        # Skip hermes and openclaw folders
        fname_lower = fname.lower()
        if 'hermes' in fname_lower or 'openclaw' in fname_lower or '.openclaw' in fname_lower or 'open claw' in fname_lower:
            skipped += 1
            continue
        unscanned.append(folder)
    
    print(f"Total folders in index: {total_folders}", flush=True)
    print(f"Skipped (Hermes/Openclaw): {skipped}", flush=True)
    print(f"Remaining to scan: {len(unscanned)}", flush=True)
    if len(unscanned) > 0:
        print(f"Estimated time: {len(unscanned) * 0.5 / 60:.1f} minutes", flush=True)
    print(flush=True)
    
    if len(unscanned) == 0:
        print("All user folders scanned!")
        return
    
    # Initialize Drive
    print("Connecting to Google Drive...", flush=True)
    drive = get_drive()
    print("Connected!", flush=True)
    
    # Scan each unscanned folder
    start_time = time.time()
    for i, folder in enumerate(unscanned):
        fid = folder['id']
        fname = folder.get('name', '')
        
        try:
            # List files in this folder
            results = drive.files().list(
                q=f"'{fid}' in parents and trashed=false",
                pageSize=200,
                fields="files(id, name, mimeType, size, modifiedTime, description)",
                orderBy="modifiedTime desc"
            ).execute()
            
            files = results.get('files', [])
            
            # Save folder scan
            scan_file = SCANS_DIR / f"{fid}.json"
            with open(scan_file, 'w') as f:
                json.dump({
                    'folder_id': fid,
                    'folder_name': fname,
                    'scanned_at': datetime.now(timezone.utc).isoformat(),
                    'files': files,
                    'file_count': len(files)
                }, f)
            
            # Progress every 50 folders
            if (i+1) % 50 == 0:
                elapsed = time.time() - start_time
                rate = (i+1) / elapsed
                eta = (len(unscanned) - i-1) / rate / 60
                print(f"[{i+1}/{len(unscanned)}] ({100*(i+1)/len(unscanned):.1f}%) ETA: {eta:.1f}min - {fname[:30]}", flush=True)
            
        except Exception as e:
            # Skip problematic folders
            continue
    
    print(f"\nDone! Total scanned: {len(scanned) + len(unscanned)} folders", flush=True)

if __name__ == '__main__':
    main()
