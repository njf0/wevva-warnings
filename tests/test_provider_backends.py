"""Focused tests for provider-specific CAP feed backends."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from wevva_warnings.backends.aemet import AEMETBackend
from wevva_warnings.backends.anmeteo import ANMETEOBackend
from wevva_warnings.backends.bahrain import BahrainBackend
from wevva_warnings.backends.bmkg import BMKGBackend
from wevva_warnings.backends.dirmet_cg import DirmetCGBackend
from wevva_warnings.backends.dwd import DWDBackend
from wevva_warnings.backends.ethiomet import EthiometBackend
from wevva_warnings.backends.fmi import FMIBackend
from wevva_warnings.backends.gmet import GMETBackend
from wevva_warnings.backends.hydrometcenter import HydrometcenterBackend
from wevva_warnings.backends.inamhi import INAMHIBackend
from wevva_warnings.backends.igebu import IGEBUBackend
from wevva_warnings.backends.indomet import INDOMETBackend
from wevva_warnings.backends.inumet import INUMETBackend
from wevva_warnings.backends.kazhydromet import KazhydrometBackend
from wevva_warnings.backends.kma import KMABackend
from wevva_warnings.backends.kyrgyzhydromet import KyrgyzhydrometBackend
from wevva_warnings.backends.meteocomores import MeteoComoresBackend
from wevva_warnings.backends.meteodjibouti import MeteoDjiboutiBackend
from wevva_warnings.backends.meteogambia import MeteoGambiaBackend
from wevva_warnings.backends.meteoguinebissau import MeteoGuineaBissauBackend
from wevva_warnings.backends.meteo_ke import MeteoKEBackend
from wevva_warnings.backends.meteomauritanie import MeteoMauritanieBackend
from wevva_warnings.backends.meteordcongo import MeteoRDCongoBackend
from wevva_warnings.backends.met_no import METNorwayBackend
from wevva_warnings.backends.meteo_sc import MeteoSCBackend
from wevva_warnings.backends.meteochile import MeteoChileBackend
from wevva_warnings.backends.meteobenin import MeteoBeninBackend
from wevva_warnings.backends.meteoburkina import MeteoBurkinaBackend
from wevva_warnings.backends.meteoliberia import MeteoLiberiaBackend
from wevva_warnings.backends.metservice_nz import MetServiceNZBackend
from wevva_warnings.backends.meteosouthsudan import MeteoSouthSudanBackend
from wevva_warnings.backends.meteosudan import MeteoSudanBackend
from wevva_warnings.backends.meteotchad import MeteoTchadBackend
from wevva_warnings.backends.meteotogo import MeteoTogoBackend
from wevva_warnings.backends.metmalawi import MetMalawiBackend
from wevva_warnings.backends.mms import MMSBackend
from wevva_warnings.backends.namem import NAMEMBackend
from wevva_warnings.backends.nimet import NiMetBackend
from wevva_warnings.backends.nve import NVEBackend
from wevva_warnings.backends.saint_lucia import SaintLuciaBackend
from wevva_warnings.backends.smn import SMNBackend
from wevva_warnings.backends.slmet import SLMETBackend
from wevva_warnings.backends.smg import SMGBackend
from wevva_warnings.backends.swic_mirror import SWICMirrorBackend
from wevva_warnings.backends.tma import TMABackend
from wevva_warnings.backends.tci import TCIBackend
from wevva_warnings.backends.ttms import TTMSBackend
from wevva_warnings.backends.uzhydromet import UzhydrometBackend
from wevva_warnings.backends.vmgd import VMGDBackend
from wevva_warnings.backends.weatherzw import WeatherZWBackend
from wevva_warnings.backends.zmd import ZMDBackend
from wevva_warnings.backends.solomon_met import SolomonMetBackend
from wevva_warnings.registry import get_source

DWD_FEED = """\
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <item>
      <title>DWD warning</title>
      <link>https://www.dwd.de/DWD/warnungen/cap-feed/en/dwd-demo.xml</link>
      <guid isPermaLink="false">https://www.dwd.de/DWD/warnungen/cap-feed/en/dwd-demo.xml</guid>
    </item>
  </channel>
</rss>
"""

AEMET_FEED = """\
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <item>
      <title>Estado completo de avisos para Galicia</title>
      <link>https://www.aemet.es/documentos_d/eltiempo/prediccion/avisos/cap/Z_CAP_C_LEMM_20260415085534_AFAC71.tar.gz</link>
      <guid>Z_CAP_C_LEMM_20260415085534_AFAC71.tar.gz</guid>
    </item>
    <item>
      <title>Aviso. Nivel amarillo. Costeros. Noroeste de A Coruña</title>
      <link>https://www.aemet.es/documentos_d/eltiempo/prediccion/avisos/cap/Z_CAP_C_LEMM_20260415085534_AFAZ711501COCO1613.xml</link>
      <guid>Z_CAP_C_LEMM_20260415085534_AFAZ711501COCO1613.xml</guid>
    </item>
  </channel>
</rss>
"""

FMI_FEED = """\
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <item>
      <title>FMI warning</title>
      <link>https://alerts.fmi.fi/cap/alert/fmi-demo.xml</link>
      <guid isPermaLink="false">urn:oid:fmi-demo</guid>
    </item>
  </channel>
</rss>
"""

MET_NO_FEED = """\
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <item>
      <title>Far away warning</title>
      <link>https://alert.met.no/weatherapi/metalerts/2.0/current?cap=met-no-far</link>
      <georss:polygon xmlns:georss="http://www.georss.org/georss">65 10 65 11 66 11 66 10 65 10</georss:polygon>
    </item>
    <item>
      <title>Matching warning</title>
      <link>https://alert.met.no/weatherapi/metalerts/2.0/current?cap=met-no-match</link>
      <georss:polygon xmlns:georss="http://www.georss.org/georss">62.9 6.4 62.9 6.8 63.2 6.8 63.2 6.4 62.9 6.4</georss:polygon>
    </item>
  </channel>
</rss>
"""

NVE_FEED = """\
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <item>
      <title>NVE warning</title>
      <link>https://api01.nve.no/hydrology/forecast/flood/v1/api/Cap/Id/nve-demo</link>
    </item>
  </channel>
</rss>
"""

BMKG_FEED = """\
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <item>
      <title>Thunderstorm Tonight in Kalimantan Tengah</title>
      <link>https://www.bmkg.go.id/alerts/nowcast/en/bmkg-demo_alert.xml</link>
      <guid isPermaLink="false">2.49.0.1.360.0.2026.04.15.demo</guid>
    </item>
    <item>
      <title>Channel self link disguised as item</title>
      <link>https://www.bmkg.go.id/alerts/nowcast/en/rss.xml</link>
    </item>
  </channel>
</rss>
"""

METEOBENIN_FEED = """\
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <item>
      <title>Vigilance météo</title>
      <link>https://www.meteobenin.bj/api/cap/meteobenin-demo.xml</link>
      <guid isPermaLink="false">urn:oid:meteobenin-demo</guid>
    </item>
  </channel>
</rss>
"""

METEOBURKINA_FEED = """\
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <item>
      <title>NAPPE DE POUSSIERE</title>
      <link>https://meteoburkina.bf/api/cap/meteoburkina-demo.xml</link>
      <guid isPermaLink="false">urn:oid:meteoburkina-demo</guid>
    </item>
  </channel>
</rss>
"""

IGEBU_FEED = """\
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <item>
      <title>Fortes précipitations</title>
      <link>https://www.igebu.bi/api/cap/igebu-demo.xml</link>
      <guid isPermaLink="false">urn:oid:igebu-demo</guid>
    </item>
  </channel>
</rss>
"""

METEOTCHAD_FEED = """\
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <item>
      <title>Vent de sable</title>
      <link>https://www.meteotchad.org/api/cap/meteotchad-demo.xml</link>
      <guid isPermaLink="false">urn:oid:meteotchad-demo</guid>
    </item>
  </channel>
</rss>
"""

METEOCOMORES_FEED = """\
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <item>
      <title>Forte houle</title>
      <link>https://meteocomores.km/api/cap/meteocomores-demo.xml</link>
      <guid isPermaLink="false">urn:oid:meteocomores-demo</guid>
    </item>
  </channel>
</rss>
"""

DIRMET_CG_FEED = """\
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <item>
      <title>Pluies modérées</title>
      <link>https://dirmet.cg/api/cap/dirmet-cg-demo.xml</link>
      <guid isPermaLink="false">urn:oid:dirmet-cg-demo</guid>
    </item>
  </channel>
</rss>
"""

METEORDCONGO_FEED = """\
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <item>
      <title>Fortes pluies</title>
      <link>https://meteordcongo.cd/api/cap/meteordcongo-demo.xml</link>
      <guid isPermaLink="false">urn:oid:meteordcongo-demo</guid>
    </item>
  </channel>
</rss>
"""

GMET_FEED = """\
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <item>
      <title>CAUTION: Rain over Coastal Ghana</title>
      <link>https://www.meteo.gov.gh/api/cap/gmet-demo.xml</link>
      <guid isPermaLink="false">urn:oid:gmet-demo</guid>
    </item>
  </channel>
</rss>
"""

ANMETEO_FEED = """\
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <item>
      <title>Orages et pluies modérés</title>
      <link>https://anmeteo.gov.gn/api/cap/anmeteo-demo.xml</link>
      <guid isPermaLink="false">urn:oid:anmeteo-demo</guid>
    </item>
  </channel>
</rss>
"""

METEOGUINEBISSAU_FEED = """\
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <item>
      <title>Boletim da alerta de altas temperaturas</title>
      <link>https://meteoguinebissau.gw/api/cap/meteoguinebissau-demo.xml</link>
      <guid isPermaLink="false">urn:oid:meteoguinebissau-demo</guid>
    </item>
  </channel>
</rss>
"""

METEOMAURITANIE_FEED = """\
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <item>
      <title>Avis d'alerte</title>
      <link>https://meteomauritanie.mr/api/cap/meteomauritanie-demo.xml</link>
      <guid isPermaLink="false">urn:oid:meteomauritanie-demo</guid>
    </item>
  </channel>
</rss>
"""

MMS_FEED = """\
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <item>
      <title>Alert white</title>
      <link>https://cap.meteorology.gov.mv/rss/alerts/2978</link>
      <guid>urn:oid:2.49.0.1.462.0.2026.4.16.7.3.48</guid>
    </item>
  </channel>
</rss>
"""

TTMS_FEED = """\
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <item>
      <title>Hazardous Seas Alert Discontinuation - Green Level</title>
      <link>https://metproducts.gov.tt/ttms/public/api/feed/846.xml</link>
      <guid isPermaLink="true">https://metproducts.gov.tt/ttms/public/api/feed/846.xml</guid>
    </item>
  </channel>
</rss>
"""

METSERVICE_NZ_FEED = """\
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <item>
      <title>Heavy Rain Warning - Orange</title>
      <link>https://alerts.metservice.com/cap/alert?id=metservice-nz-demo</link>
      <guid>metservice-nz-demo</guid>
    </item>
  </channel>
</rss>
"""

TCI_FEED = """\
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <item>
      <title>Small Craft Advisory for TCI</title>
      <link>https://cap-sources.s3.amazonaws.com/tc-gov-en/2026-03-30-15-35-39.xml</link>
      <guid>urn:oid:tci-demo</guid>
    </item>
    <item>
      <title>Ignore feed self link</title>
      <link>https://cap-sources.s3.amazonaws.com/tc-gov-en/rss.xml</link>
      <guid>rss-self</guid>
    </item>
  </channel>
</rss>
"""

VMGD_FEED = """\
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <item>
      <title>Marine strong wind warning</title>
      <link>https://cap-sources.s3.amazonaws.com/vu-vmgd-en/2026-04-06-04-16-45.xml</link>
      <guid>urn:oid:vmgd-demo</guid>
    </item>
  </channel>
</rss>
"""

INAMHI_FEED = """\
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <item>
      <title>Advertencia por lluvias y tormentas eléctricas</title>
      <link>https://cap-sources.s3.amazonaws.com/ec-inamhi-es/2026-04-16-17-22-36.xml</link>
      <guid>urn:oid:inamhi-demo</guid>
    </item>
    <item>
      <title>Ignore bulletin PDF</title>
      <link>https://www.inamhi.gob.ec/pronostico/advertencia.pdf</link>
      <guid>pdf</guid>
    </item>
  </channel>
</rss>
"""

BAHRAIN_FEED = """\
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <item>
      <title>Strong winds and high seas</title>
      <link>https://cap-sources.s3.amazonaws.com/bh-meteo-en/2026-04-16-09-09-04.xml</link>
      <guid>urn:oid:bahrain-demo</guid>
    </item>
  </channel>
</rss>
"""

NAMEM_FEED = """\
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <item>
      <title>strong wind</title>
      <link>https://cap-sources.s3.amazonaws.com/mn-namem-en/2026-04-03-08-38-31.xml</link>
      <guid>urn:oid:namem-demo</guid>
    </item>
  </channel>
</rss>
"""

NIMET_FEED = """\
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <item>
      <title>THUNDERSTORMS OVER PARTS OF NIGERIA</title>
      <link>https://cap-sources.s3.amazonaws.com/ng-nimet-en/2026-04-15-16-36-49.xml</link>
      <guid>urn:oid:nimet-demo</guid>
    </item>
  </channel>
</rss>
"""

SOLOMON_MET_FEED = """\
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <item>
      <title>Strong Wind Cancellation: Green</title>
      <link>https://cap-sources.s3.amazonaws.com/sb-met-en/2026-04-13-03-40-52.xml</link>
      <guid>urn:oid:solomon-demo</guid>
    </item>
  </channel>
</rss>
"""

METEOSOUTHSUDAN_FEED = """\
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <item>
      <title>Heat Stress expected in Northern South Sudan</title>
      <link>https://meteosouthsudan.com.ss/api/cap/meteosouthsudan-demo.xml</link>
      <guid isPermaLink="false">urn:oid:meteosouthsudan-demo</guid>
    </item>
  </channel>
</rss>
"""

METEOSUDAN_FEED = """\
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <item>
      <title>إنذار برتقالي</title>
      <link>https://meteosudan.sd/api/cap/meteosudan-demo.xml</link>
      <guid isPermaLink="false">urn:oid:meteosudan-demo</guid>
    </item>
  </channel>
</rss>
"""

ZMD_FEED = """\
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <item>
      <title>Heavy rain and thunder expected</title>
      <link>https://zmd.gov.zm/api/cap/zmd-demo.xml</link>
      <guid isPermaLink="false">urn:oid:zmd-demo</guid>
    </item>
  </channel>
</rss>
"""

WEATHERZW_FEED = """\
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <item>
      <title>Severe thunderstorms</title>
      <link>https://www.weatherzw.org.zw/api/cap/weatherzw-demo.xml</link>
      <guid isPermaLink="false">urn:oid:weatherzw-demo</guid>
    </item>
  </channel>
</rss>
"""

METEODJIBOUTI_FEED = """\
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <item>
      <title>Vent fort</title>
      <link>https://meteodjibouti.dj/api/cap/meteodjibouti-demo.xml</link>
      <guid isPermaLink="false">urn:oid:meteodjibouti-demo</guid>
    </item>
  </channel>
</rss>
"""

ETHIOMET_FEED = """\
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <item>
      <title>Heavy rainfall advisory</title>
      <link>https://www.ethiomet.gov.et/api/cap/ethiomet-demo.xml</link>
      <guid isPermaLink="false">urn:oid:ethiomet-demo</guid>
    </item>
  </channel>
</rss>
"""

METEOGAMBIA_FEED = """\
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <item>
      <title>Thunderstorm warning</title>
      <link>https://meteogambia.gm/api/cap/meteogambia-demo.xml</link>
      <guid isPermaLink="false">urn:oid:meteogambia-demo</guid>
    </item>
  </channel>
</rss>
"""

SMN_FEED = """\
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <item>
      <title>Tormentas</title>
      <link>https://ssl.smn.gob.ar/feeds/CAP/cap_salida/smn-demo.xml</link>
      <guid>https://ssl.smn.gob.ar/feeds/CAP/cap_salida/smn-demo.xml</guid>
    </item>
  </channel>
</rss>
"""

INUMET_FEED = """\
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <item>
      <title>Persistencia de lluvias abundantes</title>
      <link>https://www.inumet.gub.uy/reportes/riesgo/inumet-demo.xml</link>
      <guid isPermaLink="false">cap.inumet-demo</guid>
    </item>
  </channel>
</rss>
"""

TMA_FEED = """\
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <item>
      <title>WARNING: HEAVY RAIN</title>
      <link>https://cap-sources.s3.amazonaws.com/tz-tma-en/tma-demo.xml</link>
      <guid>urn:oid:tma-demo</guid>
    </item>
  </channel>
</rss>
"""

METEO_SC_FEED = """\
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <item>
      <title>Heavy Rain</title>
      <link>https://www.meteo.sc/api/cap/meteo-sc-demo.xml</link>
      <guid isPermaLink="false">urn:oid:meteo-sc-demo</guid>
    </item>
  </channel>
</rss>
"""

METMALAWI_FEED = """\
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <item>
      <title>Heavy rainfall warning update</title>
      <link>https://www.metmalawi.gov.mw/api/cap/metmalawi-demo.xml</link>
      <guid isPermaLink="false">urn:oid:metmalawi-demo</guid>
    </item>
  </channel>
</rss>
"""

SLMET_FEED = """\
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <item>
      <title>Dust</title>
      <link>https://slmet.gov.sl/api/cap/slmet-demo.xml</link>
      <guid isPermaLink="false">urn:oid:slmet-demo</guid>
    </item>
  </channel>
</rss>
"""

METEOTOGO_FEED = """\
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <item>
      <title>Pluie</title>
      <link>https://meteotogo.tg/api/cap/meteotogo-demo.xml</link>
      <guid isPermaLink="false">urn:oid:meteotogo-demo</guid>
    </item>
  </channel>
</rss>
"""

SAINT_LUCIA_FEED = """\
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <item>
      <title>Heavy Rain</title>
      <link>https://saint-lucia.cap-composer.wiscaribbeancmo.org/api/cap/saint-lucia-demo.xml</link>
      <guid isPermaLink="false">urn:oid:saint-lucia-demo</guid>
    </item>
  </channel>
</rss>
"""

INDOMET_FEED = """\
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <item>
      <title>Inundación</title>
      <link>https://cap-sources.s3.amazonaws.com/do-indomet-es/indomet-demo.xml</link>
      <guid isPermaLink="false">urn:oid:indomet-demo</guid>
    </item>
  </channel>
</rss>
"""

UZHYDROMET_FEED = """\
<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <title>Ветер</title>
    <link rel="alternate" href="https://meteoalert.meteoinfo.ru/uzbekistan/cap-feed/ru/human-view" />
    <link rel="related" type="application/cap+xml" href="https://meteoalert.meteoinfo.ru/uzbekistan/cap-feed/ru/uzhydromet-demo.xml" />
    <id>https://meteoalert.meteoinfo.ru/uzbekistan/cap-feed/ru/uzhydromet-demo.xml</id>
  </entry>
</feed>
"""

KAZHYDROMET_FEED = """\
<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <title>Fog</title>
    <link rel="alternate" href="https://meteoalert.meteoinfo.ru/kazakhstan/cap-feed/en/human-view" />
    <link rel="related" type="application/cap+xml" href="https://meteoalert.meteoinfo.ru/kazakhstan/cap-feed/en/kazhydromet-demo.xml" />
    <id>https://meteoalert.meteoinfo.ru/kazakhstan/cap-feed/en/kazhydromet-demo.xml</id>
  </entry>
</feed>
"""

HYDROMETCENTER_FEED = """\
<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <title>Гололедно - изморозевое отложение</title>
    <link rel="alternate" href="https://meteoinfo.ru/hmc-output/cap/cap-feed/ru/human-view" />
    <link rel="related" type="application/cap+xml" href="https://meteoinfo.ru/hmc-output/cap/cap-feed/ru/hydrometcenter-demo.xml" />
    <id>https://meteoinfo.ru/hmc-output/cap/cap-feed/ru/hydrometcenter-demo.xml</id>
  </entry>
</feed>
"""

KYRGYZHYDROMET_FEED = """\
<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <title>Wind</title>
    <link rel="alternate" href="https://meteoalert.meteoinfo.ru/kyrgyzstan/cap-feed/en/human-view" />
    <link rel="related" type="application/cap+xml" href="https://meteoalert.meteoinfo.ru/kyrgyzstan/cap-feed/en/kyrgyzhydromet-demo.xml" />
    <id>https://meteoalert.meteoinfo.ru/kyrgyzstan/cap-feed/en/kyrgyzhydromet-demo.xml</id>
  </entry>
</feed>
"""

KMA_FEED = """\
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <item>
      <title>Strong Wind Watch</title>
      <link>https://www.weather.go.kr/w/repositary/xml/wrn/xml/KR.W2604075_202604161200_SWA_75_EN.xml</link>
      <guid isPermaLink="false">KR.W2604075_202604161200_SWA_75_EN</guid>
    </item>
  </channel>
</rss>
"""

SWIC_FEED = """\
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <item>
      <title>Latest family revision</title>
      <link>https://severeweather.wmo.int/v2/cap-alerts/au-bom-en/2026/04/18/12/00/23-latest.xml</link>
      <pubDate>Sat, 18 Apr 2026 12:08:11 +0000</pubDate>
      <guid isPermaLink="false">AusBoM-IDV20600-2026-04-18T12:00:23+00:00</guid>
    </item>
    <item>
      <title>Older family revision</title>
      <link>https://severeweather.wmo.int/v2/cap-alerts/au-bom-en/2026/04/18/06/15/01-older.xml</link>
      <pubDate>Sat, 18 Apr 2026 06:17:10 +0000</pubDate>
      <guid isPermaLink="false">AusBoM-IDV20600-2026-04-18T06:15:01+00:00</guid>
    </item>
    <item>
      <title>Different family</title>
      <link>https://severeweather.wmo.int/v2/cap-alerts/au-bom-en/2026/04/18/10/45/38-other.xml</link>
      <pubDate>Sat, 18 Apr 2026 10:53:12 +0000</pubDate>
      <guid isPermaLink="false">AusBoM-IDN29000-2026-04-18T10:45:38+00:00</guid>
    </item>
  </channel>
</rss>
"""

METEO_KE_FEED = """\
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <item>
      <title>Heavy Rainfall Advisory</title>
      <link>https://meteo.go.ke/api/cap/meteo-ke-demo.xml</link>
      <guid isPermaLink="false">urn:oid:meteo-ke-demo</guid>
    </item>
  </channel>
</rss>
"""

METEOCHILE_FEED = """\
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <item>
      <title>Aviso A186/2026</title>
      <link>https://archivos.meteochile.gob.cl/portaldmc/rss/meteochile_A186_2026_cap.xml</link>
      <guid>https://archivos.meteochile.gob.cl/portaldmc/AAA/doc/evento_A186_2026.php</guid>
    </item>
  </channel>
</rss>
"""

METEOLIBERIA_FEED = """\
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <item>
      <title>Fog</title>
      <link>https://meteoliberia.com/api/cap/meteoliberia-demo.xml</link>
      <guid isPermaLink="false">urn:oid:meteoliberia-demo</guid>
    </item>
  </channel>
</rss>
"""

SMG_FEED = """\
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <item>
      <title>Macao Severe Weather Information - Monsoon</title>
      <link>https://rss.smg.gov.mo/cap_monsoon.xml</link>
      <guid isPermaLink="false">SMG-Weather_MS_2026_006_04</guid>
    </item>
  </channel>
</rss>
"""

CAP_ALERT = """\
<alert xmlns="urn:oasis:names:tc:emergency:cap:1.2">
  <identifier>{identifier}</identifier>
  <info>
    <language>{language}</language>
    <event>{event}</event>
    <headline>{headline}</headline>
    <severity>Moderate</severity>
    <description>{headline}</description>
    <area>
      <areaDesc>{area}</areaDesc>
      <polygon>{polygon}</polygon>
      {area_extras}
    </area>
    {extra_areas}
  </info>
</alert>
"""


class ProviderBackendTests(unittest.TestCase):
    def test_inumet_backend_expands_department_and_locality_area_names(self) -> None:
        backend = INUMETBackend()
        source = get_source('inumet')
        assert source is not None

        inumet_alert = """\
<cap:alert xmlns:cap="urn:oasis:names:tc:emergency:cap:1.2">
  <cap:identifier>inumet-demo</cap:identifier>
  <cap:info>
    <cap:language>es</cap:language>
    <cap:event>Lluvias</cap:event>
    <cap:headline>Persistencia de lluvias abundantes</cap:headline>
    <cap:severity>Moderate</cap:severity>
    <cap:area>
      <cap:areaDesc>Colonia : Agraciada, Campana. Flores(Todo el departamento), Tacuarembó : Achar, Clara.</cap:areaDesc>
      <cap:polygon>-34.3,-58.2 -34.1,-58.1 -34.2,-57.9 -34.3,-58.2</cap:polygon>
    </cap:area>
  </cap:info>
</cap:alert>
"""

        def fake_fetch_text(url: str, **_: object) -> str:
            documents = {
                source.url: INUMET_FEED,
                'https://www.inumet.gub.uy/reportes/riesgo/inumet-demo.xml': inumet_alert,
            }
            return documents[url]

        with (
            patch('wevva_warnings.backends._cap_feed.fetch_text', side_effect=fake_fetch_text),
            patch('wevva_warnings.backends.inumet.fetch_text', side_effect=fake_fetch_text),
        ):
            alerts = backend.fetch_alerts(source)

        self.assertEqual([alert.id for alert in alerts], ['inumet-demo'])
        self.assertEqual(alerts[0].url, 'https://www.inumet.gub.uy/reportes/riesgo/inumet-demo.xml')
        self.assertEqual(
            alerts[0].area_names,
            [
                'Colonia: Agraciada',
                'Colonia: Campana',
                'Flores',
                'Tacuarembó: Achar',
                'Tacuarembó: Clara',
            ],
        )

    def test_tma_backend_expands_region_and_island_area_names(self) -> None:
        backend = TMABackend()
        source = get_source('tma_en')
        assert source is not None

        tma_alert = """\
<cap:alert xmlns:cap="urn:oasis:names:tc:emergency:cap:1.2">
  <cap:identifier>tma-demo</cap:identifier>
  <cap:info>
    <cap:language>en</cap:language>
    <cap:event>HEAVY RAIN</cap:event>
    <cap:headline>WARNING: HEAVY RAIN</cap:headline>
    <cap:severity>Severe</cap:severity>
    <cap:area>
      <cap:areaDesc>Areas of Kilimanjaro, Arusha, Manyara, Lindi, Mtwara, Tanga, Dar es Salaam, Pwani (including Mafia Isles) together with Unguja and Pemba isles.</cap:areaDesc>
      <cap:polygon>-10.35,40.64 -9.49,39.85 -8.32,39.77 -7.75,40.16 -10.35,40.64</cap:polygon>
    </cap:area>
  </cap:info>
</cap:alert>
"""

        def fake_fetch_text(url: str, **_: object) -> str:
            documents = {
                source.url: TMA_FEED,
                'https://cap-sources.s3.amazonaws.com/tz-tma-en/tma-demo.xml': tma_alert,
            }
            return documents[url]

        with (
            patch('wevva_warnings.backends._cap_feed.fetch_text', side_effect=fake_fetch_text),
            patch('wevva_warnings.backends.tma.fetch_text', side_effect=fake_fetch_text),
        ):
            alerts = backend.fetch_alerts(source)

        self.assertEqual([alert.id for alert in alerts], ['tma-demo'])
        self.assertEqual(
            alerts[0].area_names,
            [
                'Mafia Isles',
                'Kilimanjaro',
                'Arusha',
                'Manyara',
                'Lindi',
                'Mtwara',
                'Tanga',
                'Dar es Salaam',
                'Pwani',
                'Unguja',
                'Pemba',
            ],
        )

    def test_meteo_sc_backend_splits_island_groups_into_individual_area_names(self) -> None:
        backend = MeteoSCBackend()
        source = get_source('meteo_sc')
        assert source is not None

        meteo_sc_alert = """\
<cap:alert xmlns:cap="urn:oasis:names:tc:emergency:cap:1.2">
  <cap:identifier>meteo-sc-demo</cap:identifier>
  <cap:info>
    <cap:language>en</cap:language>
    <cap:event>Heavy Rain</cap:event>
    <cap:headline>Heavy Rain Over Seychelles</cap:headline>
    <cap:severity>Moderate</cap:severity>
    <cap:area>
      <cap:areaDesc>Mahe,Praslin,La Digue,Silhouette,Bird&amp;Denis Island</cap:areaDesc>
      <cap:polygon>-4.54,55.41 -4.55,55.46 -4.60,55.49 -4.54,55.41</cap:polygon>
    </cap:area>
    <cap:area>
      <cap:areaDesc>Amirantes, Alphonse and Coetivy Island</cap:areaDesc>
      <cap:polygon>-7.29,56.05 -7.20,56.48 -6.88,56.28 -7.29,56.05</cap:polygon>
    </cap:area>
    <cap:area>
      <cap:areaDesc>Aldabra,Assumption,Cosmoledo and Farquhar Island</cap:areaDesc>
      <cap:polygon>-9.62,46.07 -9.15,46.34 -9.33,46.71 -9.62,46.07</cap:polygon>
    </cap:area>
  </cap:info>
</cap:alert>
"""

        def fake_fetch_text(url: str, **_: object) -> str:
            documents = {
                source.url: METEO_SC_FEED,
                'https://www.meteo.sc/api/cap/meteo-sc-demo.xml': meteo_sc_alert,
            }
            return documents[url]

        with (
            patch('wevva_warnings.backends._cap_feed.fetch_text', side_effect=fake_fetch_text),
            patch('wevva_warnings.backends.meteo_sc.fetch_text', side_effect=fake_fetch_text),
        ):
            alerts = backend.fetch_alerts(source)

        self.assertEqual([alert.id for alert in alerts], ['meteo-sc-demo'])
        self.assertEqual(
            alerts[0].area_names,
            [
                'Mahe',
                'Praslin',
                'La Digue',
                'Silhouette',
                'Bird Island',
                'Denis Island',
                'Amirantes',
                'Alphonse Island',
                'Coetivy Island',
                'Aldabra',
                'Assumption',
                'Cosmoledo Island',
                'Farquhar Island',
            ],
        )

    def test_metmalawi_backend_extracts_region_and_district_names_from_provider_text(self) -> None:
        backend = MetMalawiBackend()
        source = get_source('metmalawi')
        assert source is not None

        metmalawi_alert = """\
<cap:alert xmlns:cap="urn:oasis:names:tc:emergency:cap:1.2">
  <cap:identifier>metmalawi-demo</cap:identifier>
  <cap:info>
    <cap:language>en</cap:language>
    <cap:event>Rain/Wet Spell</cap:event>
    <cap:headline>HEAVY RAINFALL WARNING UPDATE</cap:headline>
    <cap:severity>Severe</cap:severity>
    <cap:description>Heavy rainfall is expected to affect most areas during the forecast period, with the highest risk over the southern, central, and lakeshore regions. Districts at high flood risk (Category 6) include Karonga, Nkhotakota, Salima, Blantyre, Thyolo, Chiradzulu, Mulanje, Mangochi, Zomba, Machinga, Ntcheu, Mwanza, and Dedza. Furthermore, runoff from the highlands continues to pose a significant flood risk in the Shire Valley districts of Chikwawa and Nsanje.</cap:description>
    <cap:audience>Areas Most Affected • Category 4: Parts of Lilongwe, Mchinji, Dowa and Ntchisi.</cap:audience>
    <cap:area>
      <cap:areaDesc>Highest risk over the southern, central, and lakes</cap:areaDesc>
      <cap:polygon>-14.42,33.75 -13.48,34.60 -15.01,35.86 -14.42,33.75</cap:polygon>
    </cap:area>
  </cap:info>
</cap:alert>
"""

        def fake_fetch_text(url: str, **_: object) -> str:
            documents = {
                source.url: METMALAWI_FEED,
                'https://www.metmalawi.gov.mw/api/cap/metmalawi-demo.xml': metmalawi_alert,
            }
            return documents[url]

        with (
            patch('wevva_warnings.backends._cap_feed.fetch_text', side_effect=fake_fetch_text),
            patch('wevva_warnings.backends.metmalawi.fetch_text', side_effect=fake_fetch_text),
        ):
            alerts = backend.fetch_alerts(source)

        self.assertEqual([alert.id for alert in alerts], ['metmalawi-demo'])
        self.assertEqual(
            alerts[0].area_names,
            [
                'Southern Region',
                'Central Region',
                'Lakeshore Areas',
                'Karonga',
                'Nkhotakota',
                'Salima',
                'Blantyre',
                'Thyolo',
                'Chiradzulu',
                'Mulanje',
                'Mangochi',
                'Zomba',
                'Machinga',
                'Ntcheu',
                'Mwanza',
                'Dedza',
                'Chikwawa',
                'Nsanje',
                'Lilongwe',
                'Mchinji',
                'Dowa',
                'Ntchisi',
            ],
        )

    def test_slmet_backend_splits_combined_area_descs(self) -> None:
        backend = SLMETBackend()
        source = get_source('slmet')
        assert source is not None

        slmet_alert = """\
<cap:alert xmlns:cap="urn:oasis:names:tc:emergency:cap:1.2">
  <cap:identifier>slmet-demo</cap:identifier>
  <cap:info>
    <cap:language>en</cap:language>
    <cap:event>Dust storm/Sandstorm</cap:event>
    <cap:headline>Dust Over Western Area</cap:headline>
    <cap:severity>Minor</cap:severity>
    <cap:area>
      <cap:areaDesc>Western Area Urban and Western Area Rural</cap:areaDesc>
      <cap:polygon>8.49,-13.29 8.42,-13.12 8.26,-13.12 8.49,-13.29</cap:polygon>
    </cap:area>
  </cap:info>
</cap:alert>
"""

        def fake_fetch_text(url: str, **_: object) -> str:
            documents = {
                source.url: SLMET_FEED,
                'https://slmet.gov.sl/api/cap/slmet-demo.xml': slmet_alert,
            }
            return documents[url]

        with (
            patch('wevva_warnings.backends._cap_feed.fetch_text', side_effect=fake_fetch_text),
            patch('wevva_warnings.backends.slmet.fetch_text', side_effect=fake_fetch_text),
        ):
            alerts = backend.fetch_alerts(source)

        self.assertEqual([alert.id for alert in alerts], ['slmet-demo'])
        self.assertEqual(
            alerts[0].area_names,
            ['Western Area Urban', 'Western Area Rural'],
        )

    def test_meteotogo_backend_collects_regions_from_provider_wording(self) -> None:
        backend = MeteoTogoBackend()
        source = get_source('meteotogo')
        assert source is not None

        meteotogo_alert = """\
<cap:alert xmlns:cap="urn:oasis:names:tc:emergency:cap:1.2">
  <cap:identifier>meteotogo-demo</cap:identifier>
  <cap:info>
    <cap:language>fr</cap:language>
    <cap:event>Pluie/période humide</cap:event>
    <cap:headline>Activités pluvio-orageuses dans les régions Maritime et Plateaux cette soirée</cap:headline>
    <cap:severity>Moderate</cap:severity>
    <cap:audience>Public vivant dans les régions Maritime et Plateaux</cap:audience>
    <cap:description>Cette soirée, les activités pluvio-orageuses modérées à fortes vont intéresser les régions des Plateaux, la Maritime et ses environs</cap:description>
    <cap:area>
      <cap:areaDesc>Maritime</cap:areaDesc>
      <cap:polygon>6.83,1.59 6.32,0.96 8.37,1.62 6.83,1.59</cap:polygon>
    </cap:area>
  </cap:info>
</cap:alert>
"""

        def fake_fetch_text(url: str, **_: object) -> str:
            documents = {
                source.url: METEOTOGO_FEED,
                'https://meteotogo.tg/api/cap/meteotogo-demo.xml': meteotogo_alert,
            }
            return documents[url]

        with (
            patch('wevva_warnings.backends._cap_feed.fetch_text', side_effect=fake_fetch_text),
            patch('wevva_warnings.backends.meteotogo.fetch_text', side_effect=fake_fetch_text),
        ):
            alerts = backend.fetch_alerts(source)

        self.assertEqual([alert.id for alert in alerts], ['meteotogo-demo'])
        self.assertEqual(alerts[0].area_names, ['Maritime', 'Plateaux'])

    def test_saint_lucia_backend_fetches_direct_cap_documents(self) -> None:
        backend = SaintLuciaBackend()
        source = get_source('saint_lucia')
        assert source is not None

        def fake_fetch_text(url: str, **_: object) -> str:
            documents = {
                source.url: SAINT_LUCIA_FEED,
                'https://saint-lucia.cap-composer.wiscaribbeancmo.org/api/cap/saint-lucia-demo.xml': CAP_ALERT.format(
                    identifier='saint-lucia-demo',
                    language='en',
                    event='Heavy Rain',
                    headline='Heavy Rain Over Saint Lucia',
                    area='Saint Lucia',
                    polygon='14.10,-60.93 13.88,-61.08 13.71,-60.93 14.10,-60.93',
                    area_extras='',
                    extra_areas='',
                ),
            }
            return documents[url]

        with patch('wevva_warnings.backends._cap_feed.fetch_text', side_effect=fake_fetch_text):
            alerts = backend.fetch_alerts(source)

        self.assertEqual([alert.id for alert in alerts], ['saint-lucia-demo'])
        self.assertEqual(
            alerts[0].url,
            'https://saint-lucia.cap-composer.wiscaribbeancmo.org/api/cap/saint-lucia-demo.xml',
        )
        self.assertEqual(alerts[0].area_names, ['Saint Lucia'])

    def test_indomet_backend_fetches_direct_cap_documents(self) -> None:
        backend = INDOMETBackend()
        source = get_source('indomet')
        assert source is not None

        def fake_fetch_text(url: str, **_: object) -> str:
            documents = {
                source.url: INDOMET_FEED,
                'https://cap-sources.s3.amazonaws.com/do-indomet-es/indomet-demo.xml': CAP_ALERT.format(
                    identifier='indomet-demo',
                    language='es',
                    event='Inundación',
                    headline='ALERTA meteorológica (PUERTO PLATA)',
                    area='PUERTO PLATA',
                    polygon='19.82,-71.25 19.70,-70.98 19.54,-70.57 19.82,-71.25',
                    area_extras='',
                    extra_areas='',
                ),
            }
            return documents[url]

        with patch('wevva_warnings.backends._cap_feed.fetch_text', side_effect=fake_fetch_text):
            alerts = backend.fetch_alerts(source)

        self.assertEqual([alert.id for alert in alerts], ['indomet-demo'])
        self.assertEqual(alerts[0].url, 'https://cap-sources.s3.amazonaws.com/do-indomet-es/indomet-demo.xml')
        self.assertEqual(alerts[0].area_names, ['PUERTO PLATA'])

    def test_uzhydromet_backend_prefers_related_cap_link(self) -> None:
        backend = UzhydrometBackend()
        source = get_source('uzhydromet_ru')
        assert source is not None

        def fake_fetch_text(url: str, **_: object) -> str:
            documents = {
                source.url: UZHYDROMET_FEED,
                'https://meteoalert.meteoinfo.ru/uzbekistan/cap-feed/ru/uzhydromet-demo.xml': CAP_ALERT.format(
                    identifier='uzhydromet-demo',
                    language='ru',
                    event='Ветер',
                    headline='Ветер',
                    area='Республика Каракалпакстан',
                    polygon='43.50,62.00 45.59,58.59 40.99,62.24 43.50,62.00',
                    area_extras='',
                    extra_areas='',
                ),
            }
            return documents[url]

        with patch('wevva_warnings.backends._cap_feed.fetch_text', side_effect=fake_fetch_text) as fetch_text:
            alerts = backend.fetch_alerts(source)

        self.assertEqual([alert.id for alert in alerts], ['uzhydromet-demo'])
        self.assertEqual(
            alerts[0].url,
            'https://meteoalert.meteoinfo.ru/uzbekistan/cap-feed/ru/uzhydromet-demo.xml',
        )
        self.assertEqual(alerts[0].area_names, ['Республика Каракалпакстан'])
        requested_urls = [call.args[0] for call in fetch_text.call_args_list]
        self.assertNotIn('https://meteoalert.meteoinfo.ru/uzbekistan/cap-feed/ru/human-view', requested_urls)

    def test_kazhydromet_backend_prefers_related_cap_link(self) -> None:
        backend = KazhydrometBackend()
        source = get_source('kazhydromet_en')
        assert source is not None

        def fake_fetch_text(url: str, **_: object) -> str:
            documents = {
                source.url: KAZHYDROMET_FEED,
                'https://meteoalert.meteoinfo.ru/kazakhstan/cap-feed/en/kazhydromet-demo.xml': CAP_ALERT.format(
                    identifier='kazhydromet-demo',
                    language='en',
                    event='Fog',
                    headline='Fog',
                    area='Munaily district (Mangystau Region)',
                    polygon='43.39,51.12 43.41,51.16 43.44,51.14 43.39,51.12',
                    area_extras='',
                    extra_areas='',
                ),
            }
            return documents[url]

        with patch('wevva_warnings.backends._cap_feed.fetch_text', side_effect=fake_fetch_text) as fetch_text:
            alerts = backend.fetch_alerts(source)

        self.assertEqual([alert.id for alert in alerts], ['kazhydromet-demo'])
        self.assertEqual(
            alerts[0].url,
            'https://meteoalert.meteoinfo.ru/kazakhstan/cap-feed/en/kazhydromet-demo.xml',
        )
        self.assertEqual(alerts[0].area_names, ['Munaily district (Mangystau Region)'])
        requested_urls = [call.args[0] for call in fetch_text.call_args_list]
        self.assertNotIn('https://meteoalert.meteoinfo.ru/kazakhstan/cap-feed/en/human-view', requested_urls)

    def test_hydrometcenter_backend_prefers_related_cap_link(self) -> None:
        backend = HydrometcenterBackend()
        source = get_source('hydrometcenter_ru')
        assert source is not None

        def fake_fetch_text(url: str, **_: object) -> str:
            documents = {
                source.url: HYDROMETCENTER_FEED,
                'https://meteoinfo.ru/hmc-output/cap/cap-feed/ru/hydrometcenter-demo.xml': CAP_ALERT.format(
                    identifier='hydrometcenter-demo',
                    language='ru',
                    event='Гололедно - изморозевое отложение',
                    headline='Гололедно - изморозевое отложение',
                    area='Ханты-Мансийский а.о.',
                    polygon='61.05,69.10 61.08,69.14 61.12,69.12 61.05,69.10',
                    area_extras='',
                    extra_areas='',
                ),
            }
            return documents[url]

        with patch('wevva_warnings.backends._cap_feed.fetch_text', side_effect=fake_fetch_text) as fetch_text:
            alerts = backend.fetch_alerts(source)

        self.assertEqual([alert.id for alert in alerts], ['hydrometcenter-demo'])
        self.assertEqual(
            alerts[0].url,
            'https://meteoinfo.ru/hmc-output/cap/cap-feed/ru/hydrometcenter-demo.xml',
        )
        self.assertEqual(alerts[0].area_names, ['Ханты-Мансийский а.о.'])
        requested_urls = [call.args[0] for call in fetch_text.call_args_list]
        self.assertNotIn('https://meteoinfo.ru/hmc-output/cap/cap-feed/ru/human-view', requested_urls)

    def test_kyrgyzhydromet_backend_prefers_related_cap_link(self) -> None:
        backend = KyrgyzhydrometBackend()
        source = get_source('kyrgyzhydromet_en')
        assert source is not None

        def fake_fetch_text(url: str, **_: object) -> str:
            documents = {
                source.url: KYRGYZHYDROMET_FEED,
                'https://meteoalert.meteoinfo.ru/kyrgyzstan/cap-feed/en/kyrgyzhydromet-demo.xml': CAP_ALERT.format(
                    identifier='kyrgyzhydromet-demo',
                    language='en',
                    event='Wind',
                    headline='Wind',
                    area='Batken district',
                    polygon='39.89,70.82 39.92,70.86 39.95,70.84 39.89,70.82',
                    area_extras='',
                    extra_areas='',
                ),
            }
            return documents[url]

        with patch('wevva_warnings.backends._cap_feed.fetch_text', side_effect=fake_fetch_text) as fetch_text:
            alerts = backend.fetch_alerts(source)

        self.assertEqual([alert.id for alert in alerts], ['kyrgyzhydromet-demo'])
        self.assertEqual(
            alerts[0].url,
            'https://meteoalert.meteoinfo.ru/kyrgyzstan/cap-feed/en/kyrgyzhydromet-demo.xml',
        )
        self.assertEqual(alerts[0].area_names, ['Batken district'])
        requested_urls = [call.args[0] for call in fetch_text.call_args_list]
        self.assertNotIn('https://meteoalert.meteoinfo.ru/kyrgyzstan/cap-feed/en/human-view', requested_urls)

    def test_kma_backend_fetches_direct_cap_documents(self) -> None:
        backend = KMABackend()
        source = get_source('kma')
        assert source is not None

        def fake_fetch_text(url: str, **_: object) -> str:
            documents = {
                source.url: KMA_FEED,
                'https://www.weather.go.kr/w/repositary/xml/wrn/xml/KR.W2604075_202604161200_SWA_75_EN.xml': CAP_ALERT.format(
                    identifier='kma-demo',
                    language='en',
                    event='Strong Wind Watch',
                    headline='Strong Wind Watch',
                    area='Ulleungdo, Dokdo',
                    polygon='37.43,130.75 37.46,130.93 37.55,130.90 37.43,130.75',
                    area_extras='',
                    extra_areas='',
                ),
            }
            return documents[url]

        with patch('wevva_warnings.backends._cap_feed.fetch_text', side_effect=fake_fetch_text) as fetch_text:
            alerts = backend.fetch_alerts(source)

        self.assertEqual([alert.id for alert in alerts], ['kma-demo'])
        self.assertEqual(
            alerts[0].url,
            'https://www.weather.go.kr/w/repositary/xml/wrn/xml/KR.W2604075_202604161200_SWA_75_EN.xml',
        )
        self.assertEqual(alerts[0].area_names, ['Ulleungdo', 'Dokdo'])
        requested_urls = [call.args[0] for call in fetch_text.call_args_list]
        self.assertNotIn('KR.W2604075_202604161200_SWA_75_EN', requested_urls)

    def test_meteo_ke_backend_fetches_direct_cap_documents(self) -> None:
        backend = MeteoKEBackend()
        source = get_source('meteo_ke')
        assert source is not None

        def fake_fetch_text(url: str, **_: object) -> str:
            documents = {
                source.url: METEO_KE_FEED,
                'https://meteo.go.ke/api/cap/meteo-ke-demo.xml': CAP_ALERT.format(
                    identifier='meteo-ke-demo',
                    language='en',
                    event='Heavy rainfall',
                    headline='Heavy Rainfall Advisory',
                    area='Most Parts of the Country',
                    polygon='-0.93,33.95 1.22,34.90 2.51,34.93 -0.93,33.95',
                    area_extras='',
                    extra_areas='',
                ),
            }
            return documents[url]

        with patch('wevva_warnings.backends._cap_feed.fetch_text', side_effect=fake_fetch_text):
            alerts = backend.fetch_alerts(source)

        self.assertEqual([alert.id for alert in alerts], ['meteo-ke-demo'])
        self.assertEqual(alerts[0].url, 'https://meteo.go.ke/api/cap/meteo-ke-demo.xml')
        self.assertEqual(alerts[0].area_names, ['Most Parts of the Country'])

    def test_meteochile_backend_prefers_cap_xml_over_html_guid(self) -> None:
        backend = MeteoChileBackend()
        source = get_source('meteochile')
        assert source is not None

        def fake_fetch_text(url: str, **_: object) -> str:
            documents = {
                source.url: METEOCHILE_FEED,
                'https://archivos.meteochile.gob.cl/portaldmc/rss/meteochile_A186_2026_cap.xml': CAP_ALERT.format(
                    identifier='meteochile-demo',
                    language='es',
                    event='Viento Normal a Moderado',
                    headline='Aviso A186/2026',
                    area='Los Lagos, Aysén',
                    polygon='-42.70,-73.80 -43.10,-72.90 -45.10,-72.40 -42.70,-73.80',
                    area_extras='',
                    extra_areas='',
                ),
            }
            return documents[url]

        with patch('wevva_warnings.backends._cap_feed.fetch_text', side_effect=fake_fetch_text) as fetch_text:
            alerts = backend.fetch_alerts(source)

        self.assertEqual([alert.id for alert in alerts], ['meteochile-demo'])
        self.assertEqual(
            alerts[0].url,
            'https://archivos.meteochile.gob.cl/portaldmc/rss/meteochile_A186_2026_cap.xml',
        )
        self.assertEqual(alerts[0].area_names, ['Los Lagos', 'Aysén'])
        requested_urls = [call.args[0] for call in fetch_text.call_args_list]
        self.assertNotIn(
            'https://archivos.meteochile.gob.cl/portaldmc/AAA/doc/evento_A186_2026.php',
            requested_urls,
        )

    def test_swic_mirror_backend_keeps_only_latest_guid_family_revision(self) -> None:
        backend = SWICMirrorBackend()
        source = get_source('bom')
        assert source is not None

        latest_url = 'https://severeweather.wmo.int/v2/cap-alerts/au-bom-en/2026/04/18/12/00/23-latest.xml'
        older_url = 'https://severeweather.wmo.int/v2/cap-alerts/au-bom-en/2026/04/18/06/15/01-older.xml'
        other_url = 'https://severeweather.wmo.int/v2/cap-alerts/au-bom-en/2026/04/18/10/45/38-other.xml'

        def fake_fetch_text(url: str, **_: object) -> str:
            documents = {
                source.url: SWIC_FEED,
                latest_url: CAP_ALERT.format(
                    identifier='swic-latest',
                    language='en',
                    event='Wind',
                    headline='Latest family revision',
                    area='Victoria',
                    polygon='-38.0,144.0 -37.9,144.2 -37.8,144.0 -38.0,144.0',
                    area_extras='',
                    extra_areas='',
                ),
                older_url: CAP_ALERT.format(
                    identifier='swic-older',
                    language='en',
                    event='Wind',
                    headline='Older family revision',
                    area='Victoria',
                    polygon='-38.0,144.0 -37.9,144.2 -37.8,144.0 -38.0,144.0',
                    area_extras='',
                    extra_areas='',
                ),
                other_url: CAP_ALERT.format(
                    identifier='swic-other',
                    language='en',
                    event='Graziers',
                    headline='Different family',
                    area='Victoria',
                    polygon='-38.1,144.1 -38.0,144.3 -37.9,144.1 -38.1,144.1',
                    area_extras='',
                    extra_areas='',
                ),
            }
            return documents[url]

        with patch('wevva_warnings.backends._cap_feed.fetch_text', side_effect=fake_fetch_text) as fetch_text:
            alerts = backend.fetch_alerts(source)

        self.assertEqual([alert.id for alert in alerts], ['swic-latest', 'swic-other'])
        requested_urls = [call.args[0] for call in fetch_text.call_args_list]
        self.assertIn(latest_url, requested_urls)
        self.assertIn(other_url, requested_urls)
        self.assertNotIn(older_url, requested_urls)

    def test_meteoliberia_backend_fetches_direct_cap_documents(self) -> None:
        backend = MeteoLiberiaBackend()
        source = get_source('meteoliberia')
        assert source is not None

        def fake_fetch_text(url: str, **_: object) -> str:
            documents = {
                source.url: METEOLIBERIA_FEED,
                'https://meteoliberia.com/api/cap/meteoliberia-demo.xml': CAP_ALERT.format(
                    identifier='meteoliberia-demo',
                    language='en',
                    event='Fog',
                    headline='WIDESPREAD FOG EXPECTED OVER PARTS OF LIBERIA',
                    area='Greenville',
                    polygon='5.05,-9.09 5.11,-9.03 5.04,-9.00 5.05,-9.09',
                    area_extras='',
                    extra_areas="""
    <area><areaDesc>Robertfield</areaDesc></area>
                    """,
                ),
            }
            return documents[url]

        with patch('wevva_warnings.backends._cap_feed.fetch_text', side_effect=fake_fetch_text):
            alerts = backend.fetch_alerts(source)

        self.assertEqual([alert.id for alert in alerts], ['meteoliberia-demo'])
        self.assertEqual(alerts[0].url, 'https://meteoliberia.com/api/cap/meteoliberia-demo.xml')
        self.assertEqual(alerts[0].area_names, ['Greenville', 'Robertfield'])

    def test_meteobenin_backend_fetches_direct_cap_documents(self) -> None:
        backend = MeteoBeninBackend()
        source = get_source('meteobenin')
        assert source is not None

        def fake_fetch_text(url: str, **_: object) -> str:
            documents = {
                source.url: METEOBENIN_FEED,
                'https://www.meteobenin.bj/api/cap/meteobenin-demo.xml': CAP_ALERT.format(
                    identifier='meteobenin-demo',
                    language='fr',
                    event='Orage',
                    headline='Vigilance météo',
                    area='Donga',
                    polygon='9.70,1.57 9.75,1.61 9.73,1.66 9.70,1.57',
                    area_extras='',
                    extra_areas='',
                ),
            }
            return documents[url]

        with patch('wevva_warnings.backends._cap_feed.fetch_text', side_effect=fake_fetch_text):
            alerts = backend.fetch_alerts(source)

        self.assertEqual([alert.id for alert in alerts], ['meteobenin-demo'])
        self.assertEqual(alerts[0].url, 'https://www.meteobenin.bj/api/cap/meteobenin-demo.xml')
        self.assertEqual(alerts[0].area_names, ['Donga'])

    def test_meteoburkina_backend_fetches_direct_cap_documents(self) -> None:
        backend = MeteoBurkinaBackend()
        source = get_source('meteoburkina')
        assert source is not None

        def fake_fetch_text(url: str, **_: object) -> str:
            documents = {
                source.url: METEOBURKINA_FEED,
                'https://meteoburkina.bf/api/cap/meteoburkina-demo.xml': CAP_ALERT.format(
                    identifier='meteoburkina-demo',
                    language='fr',
                    event='Poussière',
                    headline='NAPPE DE POUSSIERE',
                    area='Nord',
                    polygon='14.20,-0.45 14.32,-0.40 14.28,-0.18 14.20,-0.45',
                    area_extras='',
                    extra_areas='',
                ),
            }
            return documents[url]

        with patch('wevva_warnings.backends._cap_feed.fetch_text', side_effect=fake_fetch_text):
            alerts = backend.fetch_alerts(source)

        self.assertEqual([alert.id for alert in alerts], ['meteoburkina-demo'])
        self.assertEqual(alerts[0].url, 'https://meteoburkina.bf/api/cap/meteoburkina-demo.xml')
        self.assertEqual(alerts[0].area_names, ['Nord'])

    def test_igebu_backend_fetches_direct_cap_documents(self) -> None:
        backend = IGEBUBackend()
        source = get_source('igebu')
        assert source is not None

        def fake_fetch_text(url: str, **_: object) -> str:
            documents = {
                source.url: IGEBU_FEED,
                'https://www.igebu.bi/api/cap/igebu-demo.xml': CAP_ALERT.format(
                    identifier='igebu-demo',
                    language='fr',
                    event='Fortes précipitations',
                    headline='Fortes précipitations',
                    area='Mugamba',
                    polygon='-3.54,29.45 -3.48,29.51 -3.57,29.63 -3.54,29.45',
                    area_extras='',
                    extra_areas='',
                ),
            }
            return documents[url]

        with patch('wevva_warnings.backends._cap_feed.fetch_text', side_effect=fake_fetch_text):
            alerts = backend.fetch_alerts(source)

        self.assertEqual([alert.id for alert in alerts], ['igebu-demo'])
        self.assertEqual(alerts[0].url, 'https://www.igebu.bi/api/cap/igebu-demo.xml')
        self.assertEqual(alerts[0].area_names, ['Mugamba'])

    def test_meteotchad_backend_fetches_direct_cap_documents(self) -> None:
        backend = MeteoTchadBackend()
        source = get_source('meteotchad')
        assert source is not None

        def fake_fetch_text(url: str, **_: object) -> str:
            documents = {
                source.url: METEOTCHAD_FEED,
                'https://www.meteotchad.org/api/cap/meteotchad-demo.xml': CAP_ALERT.format(
                    identifier='meteotchad-demo',
                    language='fr',
                    event='Vent de sable',
                    headline='Vent de sable',
                    area='N Djamena',
                    polygon='12.05,15.00 12.15,15.08 12.08,15.17 12.05,15.00',
                    area_extras='',
                    extra_areas='',
                ),
            }
            return documents[url]

        with patch('wevva_warnings.backends._cap_feed.fetch_text', side_effect=fake_fetch_text):
            alerts = backend.fetch_alerts(source)

        self.assertEqual([alert.id for alert in alerts], ['meteotchad-demo'])
        self.assertEqual(alerts[0].url, 'https://www.meteotchad.org/api/cap/meteotchad-demo.xml')
        self.assertEqual(alerts[0].area_names, ['N Djamena'])

    def test_meteocomores_backend_fetches_direct_cap_documents(self) -> None:
        backend = MeteoComoresBackend()
        source = get_source('meteocomores')
        assert source is not None

        def fake_fetch_text(url: str, **_: object) -> str:
            documents = {
                source.url: METEOCOMORES_FEED,
                'https://meteocomores.km/api/cap/meteocomores-demo.xml': CAP_ALERT.format(
                    identifier='meteocomores-demo',
                    language='fr',
                    event='Forte houle',
                    headline='Forte houle',
                    area='Ngazidja',
                    polygon='-11.55,43.20 -11.42,43.24 -11.47,43.35 -11.55,43.20',
                    area_extras='',
                    extra_areas='',
                ),
            }
            return documents[url]

        with patch('wevva_warnings.backends._cap_feed.fetch_text', side_effect=fake_fetch_text):
            alerts = backend.fetch_alerts(source)

        self.assertEqual([alert.id for alert in alerts], ['meteocomores-demo'])
        self.assertEqual(alerts[0].url, 'https://meteocomores.km/api/cap/meteocomores-demo.xml')
        self.assertEqual(alerts[0].area_names, ['Ngazidja'])

    def test_dirmet_cg_backend_fetches_direct_cap_documents(self) -> None:
        backend = DirmetCGBackend()
        source = get_source('dirmet_cg')
        assert source is not None

        def fake_fetch_text(url: str, **_: object) -> str:
            documents = {
                source.url: DIRMET_CG_FEED,
                'https://dirmet.cg/api/cap/dirmet-cg-demo.xml': CAP_ALERT.format(
                    identifier='dirmet-cg-demo',
                    language='fr',
                    event='Pluies modérées',
                    headline='Pluies modérées',
                    area='Brazzaville',
                    polygon='-4.30,15.20 -4.22,15.28 -4.27,15.36 -4.30,15.20',
                    area_extras='',
                    extra_areas='',
                ),
            }
            return documents[url]

        with patch('wevva_warnings.backends._cap_feed.fetch_text', side_effect=fake_fetch_text):
            alerts = backend.fetch_alerts(source)

        self.assertEqual([alert.id for alert in alerts], ['dirmet-cg-demo'])
        self.assertEqual(alerts[0].url, 'https://dirmet.cg/api/cap/dirmet-cg-demo.xml')
        self.assertEqual(alerts[0].area_names, ['Brazzaville'])

    def test_meteordcongo_backend_fetches_direct_cap_documents(self) -> None:
        backend = MeteoRDCongoBackend()
        source = get_source('meteordcongo')
        assert source is not None

        def fake_fetch_text(url: str, **_: object) -> str:
            documents = {
                source.url: METEORDCONGO_FEED,
                'https://meteordcongo.cd/api/cap/meteordcongo-demo.xml': CAP_ALERT.format(
                    identifier='meteordcongo-demo',
                    language='fr',
                    event='Fortes pluies',
                    headline='Fortes pluies',
                    area='Kinshasa',
                    polygon='-4.45,15.15 -4.33,15.22 -4.40,15.36 -4.45,15.15',
                    area_extras='',
                    extra_areas='',
                ),
            }
            return documents[url]

        with patch('wevva_warnings.backends._cap_feed.fetch_text', side_effect=fake_fetch_text):
            alerts = backend.fetch_alerts(source)

        self.assertEqual([alert.id for alert in alerts], ['meteordcongo-demo'])
        self.assertEqual(alerts[0].url, 'https://meteordcongo.cd/api/cap/meteordcongo-demo.xml')
        self.assertEqual(alerts[0].area_names, ['Kinshasa'])

    def test_gmet_backend_fetches_direct_cap_documents(self) -> None:
        backend = GMETBackend()
        source = get_source('gmet')
        assert source is not None

        def fake_fetch_text(url: str, **_: object) -> str:
            documents = {
                source.url: GMET_FEED,
                'https://www.meteo.gov.gh/api/cap/gmet-demo.xml': CAP_ALERT.format(
                    identifier='gmet-demo',
                    language='en',
                    event='Rain',
                    headline='CAUTION: Rain over Coastal Ghana',
                    area='Greater Accra',
                    polygon='5.52,-0.30 5.67,-0.17 5.59,-0.05 5.52,-0.30',
                    area_extras='',
                    extra_areas='',
                ),
            }
            return documents[url]

        with patch('wevva_warnings.backends._cap_feed.fetch_text', side_effect=fake_fetch_text):
            alerts = backend.fetch_alerts(source)

        self.assertEqual([alert.id for alert in alerts], ['gmet-demo'])
        self.assertEqual(alerts[0].url, 'https://www.meteo.gov.gh/api/cap/gmet-demo.xml')
        self.assertEqual(alerts[0].area_names, ['Greater Accra'])

    def test_anmeteo_backend_fetches_direct_cap_documents(self) -> None:
        backend = ANMETEOBackend()
        source = get_source('anmeteo')
        assert source is not None

        def fake_fetch_text(url: str, **_: object) -> str:
            documents = {
                source.url: ANMETEO_FEED,
                'https://anmeteo.gov.gn/api/cap/anmeteo-demo.xml': CAP_ALERT.format(
                    identifier='anmeteo-demo',
                    language='fr',
                    event='Orages',
                    headline='Orages et pluies modérés',
                    area='Haute Guinée',
                    polygon='10.20,-10.84 10.34,-10.73 10.28,-10.60 10.20,-10.84',
                    area_extras='',
                    extra_areas='',
                ),
            }
            return documents[url]

        with patch('wevva_warnings.backends._cap_feed.fetch_text', side_effect=fake_fetch_text):
            alerts = backend.fetch_alerts(source)

        self.assertEqual([alert.id for alert in alerts], ['anmeteo-demo'])
        self.assertEqual(alerts[0].url, 'https://anmeteo.gov.gn/api/cap/anmeteo-demo.xml')
        self.assertEqual(alerts[0].area_names, ['Haute Guinée'])

    def test_meteoguinebissau_backend_fetches_direct_cap_documents(self) -> None:
        backend = MeteoGuineaBissauBackend()
        source = get_source('meteoguinebissau')
        assert source is not None

        def fake_fetch_text(url: str, **_: object) -> str:
            documents = {
                source.url: METEOGUINEBISSAU_FEED,
                'https://meteoguinebissau.gw/api/cap/meteoguinebissau-demo.xml': CAP_ALERT.format(
                    identifier='meteoguinebissau-demo',
                    language='pt',
                    event='Altas temperaturas',
                    headline='Boletim da alerta de altas temperaturas',
                    area='Oio',
                    polygon='12.14,-15.56 12.28,-15.47 12.22,-15.34 12.14,-15.56',
                    area_extras='',
                    extra_areas='',
                ),
            }
            return documents[url]

        with patch('wevva_warnings.backends._cap_feed.fetch_text', side_effect=fake_fetch_text):
            alerts = backend.fetch_alerts(source)

        self.assertEqual([alert.id for alert in alerts], ['meteoguinebissau-demo'])
        self.assertEqual(alerts[0].url, 'https://meteoguinebissau.gw/api/cap/meteoguinebissau-demo.xml')
        self.assertEqual(alerts[0].area_names, ['Oio'])

    def test_meteomauritanie_backend_fetches_direct_cap_documents(self) -> None:
        backend = MeteoMauritanieBackend()
        source = get_source('meteomauritanie')
        assert source is not None

        def fake_fetch_text(url: str, **_: object) -> str:
            documents = {
                source.url: METEOMAURITANIE_FEED,
                'https://meteomauritanie.mr/api/cap/meteomauritanie-demo.xml': CAP_ALERT.format(
                    identifier='meteomauritanie-demo',
                    language='fr',
                    event='Mer agitée',
                    headline="Avis d'alerte",
                    area='Littoral',
                    polygon='19.32,-16.95 19.48,-16.66 19.30,-16.35 19.32,-16.95',
                    area_extras='',
                    extra_areas='',
                ),
            }
            return documents[url]

        with patch('wevva_warnings.backends._cap_feed.fetch_text', side_effect=fake_fetch_text):
            alerts = backend.fetch_alerts(source)

        self.assertEqual([alert.id for alert in alerts], ['meteomauritanie-demo'])
        self.assertEqual(alerts[0].url, 'https://meteomauritanie.mr/api/cap/meteomauritanie-demo.xml')
        self.assertEqual(alerts[0].area_names, ['Littoral'])

    def test_mms_backend_fetches_numeric_alert_documents(self) -> None:
        backend = MMSBackend()
        source = get_source('mms')
        assert source is not None

        def fake_fetch_text(url: str, **_: object) -> str:
            documents = {
                source.url: MMS_FEED,
                'https://cap.meteorology.gov.mv/rss/alerts/2978': CAP_ALERT.format(
                    identifier='mms-demo',
                    language='en',
                    event='Thunderstorms, Heavy rain',
                    headline='Alert white',
                    area='From Haa Alifu Atoll to Dhaalu Atoll',
                    polygon='7.317017,72.39086 7.317017,73.94577 2.61777,73.94577 2.61777,72.39086 7.317017,72.39086',
                    area_extras='',
                    extra_areas='',
                ),
            }
            return documents[url]

        with patch('wevva_warnings.backends._cap_feed.fetch_text', side_effect=fake_fetch_text):
            alerts = backend.fetch_alerts(source)

        self.assertEqual([alert.id for alert in alerts], ['mms-demo'])
        self.assertEqual(alerts[0].url, 'https://cap.meteorology.gov.mv/rss/alerts/2978')
        self.assertEqual(alerts[0].area_names, ['From Haa Alifu Atoll to Dhaalu Atoll'])

    def test_ttms_backend_fetches_public_feed_xml_documents(self) -> None:
        backend = TTMSBackend()
        source = get_source('ttms')
        assert source is not None

        def fake_fetch_text(url: str, **_: object) -> str:
            documents = {
                source.url: TTMS_FEED,
                'https://metproducts.gov.tt/ttms/public/api/feed/846.xml': CAP_ALERT.format(
                    identifier='ttms-demo',
                    language='en',
                    event='Hazardous Seas',
                    headline='Hazardous Seas Alert Discontinuation - Green Level',
                    area='Northern and eastern exposed coastal areas',
                    polygon='11.214101,-60.78186 11.188506,-60.812073 11.195242,-60.842285 11.214101,-60.78186',
                    area_extras='',
                    extra_areas='',
                ),
            }
            return documents[url]

        with patch('wevva_warnings.backends._cap_feed.fetch_text', side_effect=fake_fetch_text):
            alerts = backend.fetch_alerts(source)

        self.assertEqual([alert.id for alert in alerts], ['ttms-demo'])
        self.assertEqual(alerts[0].url, 'https://metproducts.gov.tt/ttms/public/api/feed/846.xml')
        self.assertEqual(alerts[0].area_names, ['Northern and eastern exposed coastal areas'])

    def test_metservice_nz_backend_fetches_query_style_cap_documents(self) -> None:
        backend = MetServiceNZBackend()
        source = get_source('metservice_nz')
        assert source is not None

        def fake_fetch_text(url: str, **_: object) -> str:
            documents = {
                source.url: METSERVICE_NZ_FEED,
                'https://alerts.metservice.com/cap/alert?id=metservice-nz-demo': CAP_ALERT.format(
                    identifier='metservice-nz-demo',
                    language='en',
                    event='rain',
                    headline='Heavy Rain Warning - Orange',
                    area='Buller and Grey Districts',
                    polygon='-42.122,171.298 -42.103,171.301 -41.980,171.377 -42.122,171.298',
                    area_extras='',
                    extra_areas='',
                ),
            }
            return documents[url]

        with patch('wevva_warnings.backends._cap_feed.fetch_text', side_effect=fake_fetch_text):
            alerts = backend.fetch_alerts(source)

        self.assertEqual([alert.id for alert in alerts], ['metservice-nz-demo'])
        self.assertEqual(alerts[0].url, 'https://alerts.metservice.com/cap/alert?id=metservice-nz-demo')
        self.assertEqual(alerts[0].area_names, ['Buller and Grey Districts'])

    def test_tci_backend_fetches_language_specific_cap_documents(self) -> None:
        backend = TCIBackend()
        source = get_source('tci_en')
        assert source is not None

        def fake_fetch_text(url: str, **_: object) -> str:
            documents = {
                source.url: TCI_FEED,
                'https://cap-sources.s3.amazonaws.com/tc-gov-en/2026-03-30-15-35-39.xml': CAP_ALERT.format(
                    identifier='tci-demo',
                    language='en',
                    event='high seas',
                    headline='Small Craft Advisory for TCI',
                    area='Turks and Caicos Islands',
                    polygon='21.40,-71.90 21.40,-71.50 21.70,-71.50 21.70,-71.90 21.40,-71.90',
                    area_extras='',
                    extra_areas='',
                ),
            }
            return documents[url]

        with patch('wevva_warnings.backends._cap_feed.fetch_text', side_effect=fake_fetch_text):
            alerts = backend.fetch_alerts(source)

        self.assertEqual([alert.id for alert in alerts], ['tci-demo'])
        self.assertEqual(alerts[0].url, 'https://cap-sources.s3.amazonaws.com/tc-gov-en/2026-03-30-15-35-39.xml')
        self.assertEqual(alerts[0].area_names, ['Turks and Caicos Islands'])

    def test_vmgd_backend_fetches_cap_documents_from_provider_folder(self) -> None:
        backend = VMGDBackend()
        source = get_source('vmgd')
        assert source is not None

        def fake_fetch_text(url: str, **_: object) -> str:
            documents = {
                source.url: VMGD_FEED,
                'https://cap-sources.s3.amazonaws.com/vu-vmgd-en/2026-04-06-04-16-45.xml': CAP_ALERT.format(
                    identifier='vmgd-demo',
                    language='en',
                    event='Wind',
                    headline='Marine strong wind warning over the channel and southern waters',
                    area='The channel and southern waters.',
                    polygon='-18.97,168.81 -19.62,169.04 -20.40,169.61 -18.97,168.81',
                    area_extras='',
                    extra_areas='',
                ),
            }
            return documents[url]

        with patch('wevva_warnings.backends._cap_feed.fetch_text', side_effect=fake_fetch_text):
            alerts = backend.fetch_alerts(source)

        self.assertEqual([alert.id for alert in alerts], ['vmgd-demo'])
        self.assertEqual(alerts[0].url, 'https://cap-sources.s3.amazonaws.com/vu-vmgd-en/2026-04-06-04-16-45.xml')
        self.assertEqual(alerts[0].area_names, ['The channel and southern waters.'])

    def test_inamhi_backend_fetches_cap_documents_and_ignores_non_cap_links(self) -> None:
        backend = INAMHIBackend()
        source = get_source('inamhi')
        assert source is not None

        def fake_fetch_text(url: str, **_: object) -> str:
            documents = {
                source.url: INAMHI_FEED,
                'https://cap-sources.s3.amazonaws.com/ec-inamhi-es/2026-04-16-17-22-36.xml': CAP_ALERT.format(
                    identifier='inamhi-demo',
                    language='es',
                    event='LLUVIAS Y TORMENTAS ELÉCTRICAS',
                    headline='ADVERTENCIA POR LLUVIAS Y TORMENTAS ELÉCTRICAS',
                    area='Galápagos',
                    polygon='-0.82,-89.51 -0.81,-89.54 -0.83,-89.54 -0.82,-89.51',
                    area_extras='',
                    extra_areas='',
                ),
            }
            return documents[url]

        with patch('wevva_warnings.backends._cap_feed.fetch_text', side_effect=fake_fetch_text):
            alerts = backend.fetch_alerts(source)

        self.assertEqual([alert.id for alert in alerts], ['inamhi-demo'])
        self.assertEqual(alerts[0].url, 'https://cap-sources.s3.amazonaws.com/ec-inamhi-es/2026-04-16-17-22-36.xml')
        self.assertEqual(alerts[0].area_names, ['Galápagos'])

    def test_bahrain_backend_fetches_provider_documents(self) -> None:
        backend = BahrainBackend()
        source = get_source('bahrain_en')
        assert source is not None

        bahrain_alert = """\
<alert xmlns="urn:oasis:names:tc:emergency:cap:1.2">
  <identifier>bahrain-demo</identifier>
  <sender>metuser@mtt.gov.bh</sender>
  <status>Test</status>
  <msgType>Alert</msgType>
  <scope>Public</scope>
  <info>
    <language>en</language>
    <event>Strong winds and high seas</event>
    <headline>Strong winds and high seas</headline>
    <severity>Moderate</severity>
    <responseType>Prepare</responseType>
    <eventCode>
      <valueName>OET:v1.2</valueName>
      <value>OET-218</value>
    </eventCode>
    <senderName>metuser@mtt.gov.bh</senderName>
    <web>http://www.bahrainweather.gov.bh/</web>
    <contact>metuser@mtt.gov.bh</contact>
    <area>
      <areaDesc>The Kingdom of Bahrain and Nearby Areas</areaDesc>
      <polygon>26.68,50.59 26.62,50.43 26.32,50.30 26.68,50.59</polygon>
    </area>
  </info>
</alert>
"""

        def fake_fetch_text(url: str, **_: object) -> str:
            documents = {
                source.url: BAHRAIN_FEED,
                'https://cap-sources.s3.amazonaws.com/bh-meteo-en/2026-04-16-09-09-04.xml': bahrain_alert,
            }
            return documents[url]

        with patch('wevva_warnings.backends._cap_feed.fetch_text', side_effect=fake_fetch_text):
            alerts = backend.fetch_alerts(source)

        self.assertEqual([alert.id for alert in alerts], ['bahrain-demo'])
        self.assertEqual(alerts[0].url, 'https://cap-sources.s3.amazonaws.com/bh-meteo-en/2026-04-16-09-09-04.xml')
        self.assertEqual(alerts[0].area_names, ['The Kingdom of Bahrain and Nearby Areas'])

    def test_namem_backend_fetches_provider_documents(self) -> None:
        backend = NAMEMBackend()
        source = get_source('namem_en')
        assert source is not None

        namem_alert = """\
<alert xmlns="urn:oasis:names:tc:emergency:cap:1.2">
  <identifier>namem-demo</identifier>
  <sender>oyunjargal@namem.gov.mn</sender>
  <status>Actual</status>
  <msgType>Alert</msgType>
  <scope>Public</scope>
  <info>
    <language>en</language>
    <event>strong wind</event>
    <headline>strong wind</headline>
    <severity>Severe</severity>
    <responseType>Prepare</responseType>
    <senderName>NAMEM Mongolia</senderName>
    <web>http://weather.gov.mn</web>
    <contact>o_jargal@hotmail.com</contact>
    <eventCode>
      <valueName>OET:v1.2</valueName>
      <value>OET-218</value>
    </eventCode>
    <area>
      <areaDesc>Western, Soutern, Eastern of Mongolia</areaDesc>
      <polygon>43.00,98.83 42.52,99.62 42.48,101.33 43.00,98.83</polygon>
    </area>
  </info>
</alert>
"""

        def fake_fetch_text(url: str, **_: object) -> str:
            documents = {
                source.url: NAMEM_FEED,
                'https://cap-sources.s3.amazonaws.com/mn-namem-en/2026-04-03-08-38-31.xml': namem_alert,
            }
            return documents[url]

        with patch('wevva_warnings.backends._cap_feed.fetch_text', side_effect=fake_fetch_text):
            alerts = backend.fetch_alerts(source)

        self.assertEqual([alert.id for alert in alerts], ['namem-demo'])
        self.assertEqual(alerts[0].url, 'https://cap-sources.s3.amazonaws.com/mn-namem-en/2026-04-03-08-38-31.xml')
        self.assertEqual(alerts[0].area_names, ['Western', 'Soutern', 'Eastern of Mongolia'])

    def test_nimet_backend_fetches_provider_documents(self) -> None:
        backend = NiMetBackend()
        source = get_source('nimet_en')
        assert source is not None

        nimet_alert = """\
<alert xmlns="urn:oasis:names:tc:emergency:cap:1.2">
  <identifier>nimet-demo</identifier>
  <sender>cfo@nimet.gov.ng</sender>
  <status>Actual</status>
  <msgType>Alert</msgType>
  <scope>Public</scope>
  <info>
    <language>en</language>
    <event>THUNDERSTORMS</event>
    <headline>THUNDERSTORMS OVER PARTS OF NIGERIA</headline>
    <severity>Severe</severity>
    <responseType>Prepare</responseType>
    <senderName>NiMet, Nigeria</senderName>
    <web>http://www.nimet.gov.ng</web>
    <contact>nimetng@gmail.com</contact>
    <eventCode>
      <valueName>OET:v1.2</valueName>
      <value>OET-194</value>
    </eventCode>
    <area>
      <areaDesc>Some states in Nigeria will be affected.</areaDesc>
      <polygon>11.62,9.56 11.20,10.03 10.52,6.68 11.62,9.56</polygon>
    </area>
  </info>
</alert>
"""

        def fake_fetch_text(url: str, **_: object) -> str:
            documents = {
                source.url: NIMET_FEED,
                'https://cap-sources.s3.amazonaws.com/ng-nimet-en/2026-04-15-16-36-49.xml': nimet_alert,
            }
            return documents[url]

        with patch('wevva_warnings.backends._cap_feed.fetch_text', side_effect=fake_fetch_text):
            alerts = backend.fetch_alerts(source)

        self.assertEqual([alert.id for alert in alerts], ['nimet-demo'])
        self.assertEqual(alerts[0].url, 'https://cap-sources.s3.amazonaws.com/ng-nimet-en/2026-04-15-16-36-49.xml')
        self.assertEqual(alerts[0].area_names, ['Some states in Nigeria will be affected.'])

    def test_solomon_met_backend_fetches_provider_documents(self) -> None:
        backend = SolomonMetBackend()
        source = get_source('solomon_met')
        assert source is not None

        solomon_alert = """\
<alert xmlns="urn:oasis:names:tc:emergency:cap:1.2">
  <identifier>solomon-demo</identifier>
  <sender>forecast@met.gov.sb</sender>
  <status>Actual</status>
  <msgType>Update</msgType>
  <scope>Public</scope>
  <references>forecast@met.gov.sb,older-solomon-demo,2026-04-12T18:30:13+11:00</references>
  <info>
    <language>en</language>
    <event>Strong Wind</event>
    <headline>Strong Wind Cancellation: Green</headline>
    <severity>Minor</severity>
    <responseType>None</responseType>
    <senderName>Solomon Islands Met Service</senderName>
    <web>https://www.facebook.com/groups/SIweather</web>
    <eventCode>
      <valueName>OET:v1.2</valueName>
      <value>OET-218</value>
    </eventCode>
    <area>
      <areaDesc>Western province</areaDesc>
      <polygon>-7.28,156.51 -6.96,155.92 -7.07,155.35 -7.28,156.51</polygon>
    </area>
  </info>
</alert>
"""

        def fake_fetch_text(url: str, **_: object) -> str:
            documents = {
                source.url: SOLOMON_MET_FEED,
                'https://cap-sources.s3.amazonaws.com/sb-met-en/2026-04-13-03-40-52.xml': solomon_alert,
            }
            return documents[url]

        with patch('wevva_warnings.backends._cap_feed.fetch_text', side_effect=fake_fetch_text):
            alerts = backend.fetch_alerts(source)

        self.assertEqual([alert.id for alert in alerts], ['solomon-demo'])
        self.assertEqual(alerts[0].url, 'https://cap-sources.s3.amazonaws.com/sb-met-en/2026-04-13-03-40-52.xml')
        self.assertEqual(alerts[0].area_names, ['Western province'])

    def test_metservice_nz_backend_preserves_warning_parameters(self) -> None:
        backend = MetServiceNZBackend()
        source = get_source('metservice_nz')
        assert source is not None

        metservice_parameter_alert = """\
<alert xmlns="urn:oasis:names:tc:emergency:cap:1.2">
  <identifier>metservice-nz-parameters</identifier>
  <info>
    <language>en</language>
    <event>rain</event>
    <headline>Heavy Rain Warning - Orange</headline>
    <severity>Moderate</severity>
    <parameter>
      <valueName>ChanceOfUpgrade</valueName>
      <value>Minimal</value>
    </parameter>
    <parameter>
      <valueName>ColourCode</valueName>
      <value>Orange</value>
    </parameter>
    <parameter>
      <valueName>ColourCodeHex</valueName>
      <value>#FF8918</value>
    </parameter>
    <parameter>
      <valueName>NextUpdate</valueName>
      <value>2026-04-17T10:00:00+12:00</value>
    </parameter>
    <area>
      <areaDesc>Buller and Grey Districts</areaDesc>
      <polygon>-42.122,171.298 -42.103,171.301 -41.980,171.377 -42.122,171.298</polygon>
    </area>
  </info>
</alert>
"""

        def fake_fetch_text(url: str, **_: object) -> str:
            documents = {
                source.url: METSERVICE_NZ_FEED,
                'https://alerts.metservice.com/cap/alert?id=metservice-nz-demo': metservice_parameter_alert,
            }
            return documents[url]

        with patch('wevva_warnings.backends._cap_feed.fetch_text', side_effect=fake_fetch_text):
            alerts = backend.fetch_alerts(source)

        self.assertEqual([alert.id for alert in alerts], ['metservice-nz-parameters'])
        self.assertEqual(
            alerts[0].parameters,
            {
                'ChanceOfUpgrade': ['Minimal'],
                'ColourCode': ['Orange'],
                'ColourCodeHex': ['#FF8918'],
                'NextUpdate': ['2026-04-17T10:00:00+12:00'],
            },
        )

    def test_meteosouthsudan_backend_fetches_direct_cap_documents(self) -> None:
        backend = MeteoSouthSudanBackend()
        source = get_source('meteosouthsudan')
        assert source is not None

        def fake_fetch_text(url: str, **_: object) -> str:
            documents = {
                source.url: METEOSOUTHSUDAN_FEED,
                'https://meteosouthsudan.com.ss/api/cap/meteosouthsudan-demo.xml': CAP_ALERT.format(
                    identifier='meteosouthsudan-demo',
                    language='en',
                    event='Heat Stress',
                    headline='Heat Stress expected in Northern South Sudan',
                    area='Warrap State',
                    polygon='8.40,28.10 8.54,28.24 8.45,28.39 8.40,28.10',
                    area_extras='',
                    extra_areas='',
                ),
            }
            return documents[url]

        with patch('wevva_warnings.backends._cap_feed.fetch_text', side_effect=fake_fetch_text):
            alerts = backend.fetch_alerts(source)

        self.assertEqual([alert.id for alert in alerts], ['meteosouthsudan-demo'])
        self.assertEqual(alerts[0].url, 'https://meteosouthsudan.com.ss/api/cap/meteosouthsudan-demo.xml')
        self.assertEqual(alerts[0].area_names, ['Warrap State'])

    def test_meteosudan_backend_fetches_direct_cap_documents(self) -> None:
        backend = MeteoSudanBackend()
        source = get_source('meteosudan')
        assert source is not None

        def fake_fetch_text(url: str, **_: object) -> str:
            documents = {
                source.url: METEOSUDAN_FEED,
                'https://meteosudan.sd/api/cap/meteosudan-demo.xml': CAP_ALERT.format(
                    identifier='meteosudan-demo',
                    language='ar',
                    event='موجة حر',
                    headline='إنذار برتقالي',
                    area='ولاية الخرطوم',
                    polygon='15.40,32.42 15.56,32.53 15.46,32.68 15.40,32.42',
                    area_extras='',
                    extra_areas='',
                ),
            }
            return documents[url]

        with patch('wevva_warnings.backends._cap_feed.fetch_text', side_effect=fake_fetch_text):
            alerts = backend.fetch_alerts(source)

        self.assertEqual([alert.id for alert in alerts], ['meteosudan-demo'])
        self.assertEqual(alerts[0].url, 'https://meteosudan.sd/api/cap/meteosudan-demo.xml')
        self.assertEqual(alerts[0].area_names, ['ولاية الخرطوم'])

    def test_zmd_backend_fetches_direct_cap_documents(self) -> None:
        backend = ZMDBackend()
        source = get_source('zmd')
        assert source is not None

        def fake_fetch_text(url: str, **_: object) -> str:
            documents = {
                source.url: ZMD_FEED,
                'https://zmd.gov.zm/api/cap/zmd-demo.xml': CAP_ALERT.format(
                    identifier='zmd-demo',
                    language='en',
                    event='Heavy rain',
                    headline='Heavy rain and thunder expected',
                    area='Livingstone',
                    polygon='-17.90,25.76 -17.80,25.89 -17.93,26.00 -17.90,25.76',
                    area_extras='',
                    extra_areas='',
                ),
            }
            return documents[url]

        with patch('wevva_warnings.backends._cap_feed.fetch_text', side_effect=fake_fetch_text):
            alerts = backend.fetch_alerts(source)

        self.assertEqual([alert.id for alert in alerts], ['zmd-demo'])
        self.assertEqual(alerts[0].url, 'https://zmd.gov.zm/api/cap/zmd-demo.xml')
        self.assertEqual(alerts[0].area_names, ['Livingstone'])

    def test_weatherzw_backend_fetches_direct_cap_documents(self) -> None:
        backend = WeatherZWBackend()
        source = get_source('weatherzw')
        assert source is not None

        def fake_fetch_text(url: str, **_: object) -> str:
            documents = {
                source.url: WEATHERZW_FEED,
                'https://www.weatherzw.org.zw/api/cap/weatherzw-demo.xml': CAP_ALERT.format(
                    identifier='weatherzw-demo',
                    language='en',
                    event='Severe thunderstorms',
                    headline='Severe thunderstorms',
                    area='Matabeleland South',
                    polygon='-20.50,28.90 -20.34,29.06 -20.47,29.20 -20.50,28.90',
                    area_extras='',
                    extra_areas='',
                ),
            }
            return documents[url]

        with patch('wevva_warnings.backends._cap_feed.fetch_text', side_effect=fake_fetch_text):
            alerts = backend.fetch_alerts(source)

        self.assertEqual([alert.id for alert in alerts], ['weatherzw-demo'])
        self.assertEqual(alerts[0].url, 'https://www.weatherzw.org.zw/api/cap/weatherzw-demo.xml')
        self.assertEqual(alerts[0].area_names, ['Matabeleland South'])

    def test_meteodjibouti_backend_fetches_direct_cap_documents(self) -> None:
        backend = MeteoDjiboutiBackend()
        source = get_source('meteodjibouti')
        assert source is not None

        def fake_fetch_text(url: str, **_: object) -> str:
            documents = {
                source.url: METEODJIBOUTI_FEED,
                'https://meteodjibouti.dj/api/cap/meteodjibouti-demo.xml': CAP_ALERT.format(
                    identifier='meteodjibouti-demo',
                    language='fr',
                    event='Vent fort',
                    headline='Vent fort',
                    area='Djibouti',
                    polygon='11.54,43.12 11.60,43.14 11.58,43.19 11.54,43.12',
                    area_extras='',
                    extra_areas='',
                ),
            }
            return documents[url]

        with patch('wevva_warnings.backends._cap_feed.fetch_text', side_effect=fake_fetch_text):
            alerts = backend.fetch_alerts(source)

        self.assertEqual([alert.id for alert in alerts], ['meteodjibouti-demo'])
        self.assertEqual(alerts[0].url, 'https://meteodjibouti.dj/api/cap/meteodjibouti-demo.xml')
        self.assertEqual(alerts[0].area_names, ['Djibouti'])

    def test_ethiomet_backend_fetches_direct_cap_documents(self) -> None:
        backend = EthiometBackend()
        source = get_source('ethiomet')
        assert source is not None

        def fake_fetch_text(url: str, **_: object) -> str:
            documents = {
                source.url: ETHIOMET_FEED,
                'https://www.ethiomet.gov.et/api/cap/ethiomet-demo.xml': CAP_ALERT.format(
                    identifier='ethiomet-demo',
                    language='en',
                    event='Heavy rainfall',
                    headline='Heavy rainfall advisory',
                    area='Afar',
                    polygon='11.80,40.42 11.92,40.51 11.85,40.62 11.80,40.42',
                    area_extras='',
                    extra_areas='',
                ),
            }
            return documents[url]

        with patch('wevva_warnings.backends._cap_feed.fetch_text', side_effect=fake_fetch_text):
            alerts = backend.fetch_alerts(source)

        self.assertEqual([alert.id for alert in alerts], ['ethiomet-demo'])
        self.assertEqual(alerts[0].url, 'https://www.ethiomet.gov.et/api/cap/ethiomet-demo.xml')
        self.assertEqual(alerts[0].area_names, ['Afar'])

    def test_meteogambia_backend_fetches_direct_cap_documents(self) -> None:
        backend = MeteoGambiaBackend()
        source = get_source('meteogambia')
        assert source is not None

        def fake_fetch_text(url: str, **_: object) -> str:
            documents = {
                source.url: METEOGAMBIA_FEED,
                'https://meteogambia.gm/api/cap/meteogambia-demo.xml': CAP_ALERT.format(
                    identifier='meteogambia-demo',
                    language='en',
                    event='Thunderstorm',
                    headline='Thunderstorm warning',
                    area='West Coast Region',
                    polygon='13.11,-16.88 13.23,-16.76 13.16,-16.66 13.11,-16.88',
                    area_extras='',
                    extra_areas='',
                ),
            }
            return documents[url]

        with patch('wevva_warnings.backends._cap_feed.fetch_text', side_effect=fake_fetch_text):
            alerts = backend.fetch_alerts(source)

        self.assertEqual([alert.id for alert in alerts], ['meteogambia-demo'])
        self.assertEqual(alerts[0].url, 'https://meteogambia.gm/api/cap/meteogambia-demo.xml')
        self.assertEqual(alerts[0].area_names, ['West Coast Region'])

    def test_smg_backend_fetches_fixed_cap_documents(self) -> None:
        backend = SMGBackend()
        source = get_source('smg')
        assert source is not None

        smg_alert = """\
<alert xmlns="urn:oasis:names:tc:emergency:cap:1.2">
  <identifier>smg-demo</identifier>
  <info>
    <language>en</language>
    <event>STRONG MONSOON SIGNAL</event>
    <headline>Strong monsoon signal cancelled</headline>
    <severity>Moderate</severity>
    <urgency>Past</urgency>
    <certainty>Observed</certainty>
    <area>
      <areaDesc>Macao SAR Administrative Area Map</areaDesc>
      <polygon>22.0766,113.5709 22.1656,113.6301 22.2160,113.5520 22.0766,113.5709</polygon>
    </area>
  </info>
</alert>
"""

        def fake_fetch_text(url: str, **_: object) -> str:
            documents = {
                source.url: SMG_FEED,
                'https://rss.smg.gov.mo/cap_monsoon.xml': smg_alert,
            }
            return documents[url]

        with patch('wevva_warnings.backends._cap_feed.fetch_text', side_effect=fake_fetch_text):
            alerts = backend.fetch_alerts(source)

        self.assertEqual([alert.id for alert in alerts], ['smg-demo'])
        self.assertEqual(alerts[0].url, 'https://rss.smg.gov.mo/cap_monsoon.xml')
        self.assertEqual(alerts[0].area_names, ['Macao SAR Administrative Area Map'])

    def test_bmkg_backend_fetches_direct_alert_documents(self) -> None:
        backend = BMKGBackend()
        source = get_source('bmkg_en')
        assert source is not None

        def fake_fetch_text(url: str, **_: object) -> str:
            documents = {
                source.url: BMKG_FEED,
                'https://www.bmkg.go.id/alerts/nowcast/en/bmkg-demo_alert.xml': CAP_ALERT.format(
                    identifier='bmkg-demo',
                    language='en',
                    event='Thunderstorm',
                    headline='Thunderstorm Tonight in Kalimantan Tengah',
                    area='Kalimantan Tengah',
                    polygon='-0.666,114.369 -0.688,114.353 -0.695,114.350 -0.666,114.369',
                    area_extras='',
                    extra_areas='',
                ),
            }
            return documents[url]

        with patch('wevva_warnings.backends._cap_feed.fetch_text', side_effect=fake_fetch_text) as fetch_text:
            alerts = backend.fetch_alerts(source)

        self.assertEqual([alert.id for alert in alerts], ['bmkg-demo'])
        self.assertEqual(
            alerts[0].url,
            'https://www.bmkg.go.id/alerts/nowcast/en/bmkg-demo_alert.xml',
        )
        self.assertEqual(alerts[0].area_names, ['Kalimantan Tengah'])
        requested_urls = [call.args[0] for call in fetch_text.call_args_list]
        self.assertNotIn('https://www.bmkg.go.id/alerts/nowcast/en/rss.xml', requested_urls)

    def test_aemet_backend_skips_full_state_archive_and_fetches_cap_documents(self) -> None:
        backend = AEMETBackend()
        source = get_source('aemet')
        assert source is not None

        def fake_fetch_text(url: str, **_: object) -> str:
            documents = {
                source.url: AEMET_FEED,
                'https://www.aemet.es/documentos_d/eltiempo/prediccion/avisos/cap/Z_CAP_C_LEMM_20260415085534_AFAZ711501COCO1613.xml': CAP_ALERT.format(
                    identifier='aemet-demo',
                    language='en-GB',
                    event='Moderate coastalevent warning',
                    headline='Moderate coastalevent warning. Costa - Noroeste de A Coruña',
                    area='Costa - Noroeste de A Coruña',
                    polygon='43.46,-9.42 43.48,-9.34 43.51,-9.31 43.46,-9.42',
                    area_extras="""
      <geocode><valueName>AEMET-Meteoalerta zona</valueName><value>711501C</value></geocode>
                    """,
                    extra_areas='',
                ),
            }
            return documents[url]

        with patch('wevva_warnings.backends._cap_feed.fetch_text', side_effect=fake_fetch_text) as fetch_text:
            alerts = backend.fetch_alerts(source)

        self.assertEqual([alert.id for alert in alerts], ['aemet-demo'])
        self.assertEqual(
            alerts[0].url,
            'https://www.aemet.es/documentos_d/eltiempo/prediccion/avisos/cap/Z_CAP_C_LEMM_20260415085534_AFAZ711501COCO1613.xml',
        )
        self.assertEqual(alerts[0].area_names, ['Costa - Noroeste de A Coruña'])
        self.assertEqual(alerts[0].geocodes, {'AEMET-Meteoalerta zona': ['711501C']})

        requested_urls = [call.args[0] for call in fetch_text.call_args_list]
        self.assertNotIn(
            'https://www.aemet.es/documentos_d/eltiempo/prediccion/avisos/cap/Z_CAP_C_LEMM_20260415085534_AFAC71.tar.gz',
            requested_urls,
        )

    def test_dwd_backend_fetches_linked_cap_documents(self) -> None:
        backend = DWDBackend()
        source = get_source('dwd_en')
        assert source is not None

        def fake_fetch_text(url: str, **_: object) -> str:
            documents = {
                source.url: DWD_FEED,
                'https://www.dwd.de/DWD/warnungen/cap-feed/en/dwd-demo.xml': CAP_ALERT.format(
                    identifier='dwd-demo',
                    language='en-GB',
                    event='Wind warning',
                    headline='DWD headline',
                    area='Germany',
                    polygon='49.7,7.5 49.7,7.8 49.9,7.8 49.9,7.5 49.7,7.5',
                    area_extras="""
      <geocode><valueName>EXCLUDE_POLYGON</valueName><value>49.75,7.55 49.76,7.56 49.75,7.55</value></geocode>
      <altitude>0.0</altitude>
      <ceiling>9842.5</ceiling>
                    """,
                    extra_areas="""
    <area><areaDesc>Nordfriesische Küste</areaDesc><geocode><valueName>WARNCELLID</valueName><value>501000005</value></geocode></area>
                    """,
                ),
            }
            return documents[url]

        with patch('wevva_warnings.backends._cap_feed.fetch_text', side_effect=fake_fetch_text):
            alerts = backend.fetch_alerts(source)

        self.assertEqual([alert.id for alert in alerts], ['dwd-demo'])
        self.assertEqual(alerts[0].url, 'https://www.dwd.de/DWD/warnungen/cap-feed/en/dwd-demo.xml')
        self.assertEqual(alerts[0].area_names, ['Germany', 'Nordfriesische Küste'])
        self.assertEqual(
            alerts[0].geocodes,
            {
                'EXCLUDE_POLYGON': ['49.75,7.55 49.76,7.56 49.75,7.55'],
                'WARNCELLID': ['501000005'],
            },
        )

    def test_fmi_backend_fetches_linked_cap_documents(self) -> None:
        backend = FMIBackend()
        source = get_source('fmi_en')
        assert source is not None

        def fake_fetch_text(url: str, **_: object) -> str:
            documents = {
                source.url: FMI_FEED,
                'https://alerts.fmi.fi/cap/alert/fmi-demo.xml': CAP_ALERT.format(
                    identifier='fmi-demo',
                    language='en-GB',
                    event='Wind warning',
                    headline='FMI headline',
                    area='Finland',
                    polygon='60.15,24.85 60.15,25.05 60.30,25.05 60.30,24.85 60.15,24.85',
                    area_extras="""
      <geocode><valueName>METAREA</valueName><value>B4W</value></geocode>
                    """,
                    extra_areas='',
                ),
            }
            return documents[url]

        with patch('wevva_warnings.backends._cap_feed.fetch_text', side_effect=fake_fetch_text):
            alerts = backend.fetch_alerts(source)

        self.assertEqual([alert.id for alert in alerts], ['fmi-demo'])
        self.assertEqual(alerts[0].url, 'https://alerts.fmi.fi/cap/alert/fmi-demo.xml')
        self.assertEqual(alerts[0].area_names, ['Finland'])
        self.assertEqual(alerts[0].geocodes, {'METAREA': ['B4W']})

    def test_met_norway_backend_prefilters_feed_items_by_georss_polygon(self) -> None:
        backend = METNorwayBackend()
        source = get_source('met_no')
        assert source is not None

        def fake_fetch_text(url: str, **_: object) -> str:
            documents = {
                source.url: MET_NO_FEED,
                'https://alert.met.no/weatherapi/metalerts/2.0/current?cap=met-no-match': CAP_ALERT.format(
                    identifier='met-no-match',
                    language='en',
                    event='Gale warning',
                    headline='MET Norway headline',
                    area='Ona - Halten',
                    polygon='62.9,6.4 62.9,6.8 63.2,6.8 63.2,6.4 62.9,6.4',
                    area_extras="""
      <altitude>0</altitude>
      <ceiling>900</ceiling>
                    """,
                    extra_areas='',
                ),
            }
            return documents[url]

        with patch('wevva_warnings.backends._cap_feed.fetch_text', side_effect=fake_fetch_text) as fetch_text:
            alerts = backend.fetch_alerts(source, lat=63.0, lon=6.6)

        self.assertEqual([alert.id for alert in alerts], ['met-no-match'])
        requested_urls = [call.args[0] for call in fetch_text.call_args_list]
        self.assertNotIn('https://alert.met.no/weatherapi/metalerts/2.0/current?cap=met-no-far', requested_urls)
        self.assertEqual(alerts[0].area_names, ['Ona - Halten'])
        self.assertEqual(alerts[0].geocodes, {})

    def test_nve_backend_fetches_linked_cap_documents(self) -> None:
        backend = NVEBackend()
        source = get_source('nve')
        assert source is not None

        def fake_fetch_text(url: str, **_: object) -> str:
            documents = {
                source.url: NVE_FEED,
                'https://api01.nve.no/hydrology/forecast/flood/v1/api/Cap/Id/nve-demo': CAP_ALERT.format(
                    identifier='nve-demo',
                    language='en',
                    event='Flood warning',
                    headline='NVE headline',
                    area='Ofoten',
                    polygon='68.35,17.2 68.35,17.7 68.55,17.7 68.55,17.2 68.35,17.2',
                    area_extras="""
      <geocode><valueName>AvalancheRegionId</valueName><value>3015</value></geocode>
                    """,
                    extra_areas='',
                ),
            }
            return documents[url]

        with patch('wevva_warnings.backends._cap_feed.fetch_text', side_effect=fake_fetch_text):
            alerts = backend.fetch_alerts(source)

        self.assertEqual([alert.id for alert in alerts], ['nve-demo'])
        self.assertEqual(alerts[0].url, 'https://api01.nve.no/hydrology/forecast/flood/v1/api/Cap/Id/nve-demo')
        self.assertEqual(alerts[0].area_names, ['Ofoten'])
        self.assertEqual(alerts[0].geocodes, {'AvalancheRegionId': ['3015']})

    def test_smn_backend_fetches_feed_cap_documents(self) -> None:
        backend = SMNBackend()
        source = get_source('smn')
        assert source is not None

        def fake_fetch_text(url: str, **_: object) -> str:
            documents = {
                source.url: SMN_FEED,
                'https://ssl.smn.gob.ar/feeds/CAP/cap_salida/smn-demo.xml': CAP_ALERT.format(
                    identifier='smn-demo',
                    language='es-AR',
                    event='Tormentas',
                    headline='Tormentas',
                    area='Buenos Aires',
                    polygon='-34.80,-58.60 -34.80,-58.20 -34.40,-58.20 -34.80,-58.60',
                    area_extras='',
                    extra_areas='',
                ),
            }
            return documents[url]

        with patch('wevva_warnings.backends._cap_feed.fetch_text', side_effect=fake_fetch_text):
            alerts = backend.fetch_alerts(source)

        self.assertEqual([alert.id for alert in alerts], ['smn-demo'])
        self.assertEqual(alerts[0].url, 'https://ssl.smn.gob.ar/feeds/CAP/cap_salida/smn-demo.xml')
        self.assertEqual(alerts[0].area_names, ['Buenos Aires'])
