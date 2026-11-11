import json, re, sys
from collections import Counter
NAME = [  # checked in order against itinerary name
 ('Alaska', r'alaska|inside passage'),
 ('Hawaii', r'hawai'),
 ('Panama Canal', r'panama canal'),
 ('Bermuda', r'bermuda'),
 ('Canada & New England', r'new england|canada|canadian|maritimes'),
 ('British Isles', r'british isles|ireland|scotland|scottish|united kingdom|\buk\b'),
 ('Galapagos', r'galapagos|gal[aá]pagos'),
 ('Antarctica & South America', r'south america|antarctic|patagonia|brazil|argentin|chile|cape horn|amazon'),
 ('Australia & New Zealand', r'australia|new zealand|tasmania|queensland|seacation|great barrier|hunter coast'),
 ('South Pacific', r'south pacific|fiji|tahiti|polynesia|vanuatu|new caledonia'),
 ('Asia', r'japan|asia|china|korea|vietnam|thailand|singapore|malaysia|taiwan|philippines|india\b|hong kong|bali|indonesia'),
 ('Middle East', r'emirates|dubai|arabian|middle east|qatar|oman|red sea|saudi'),
 ('Northern Europe', r'norw|fjord|baltic|iceland|northern europe|scandinavia|arctic|north cape|greenland|northern lights|midnight sun'),
 ('Mediterranean', r'mediterranean|greek|greece|aegean|adriatic|italy|italian|spain|spanish|france|french riviera|croatia|turkey|holy land|iberia|portugal|riviera'),
 ('Africa & Canary Islands', r'africa|canary|canaries|madeira|morocco|seychelles|mauritius'),
 ('River Cruise', r'\brhine|danube|\briver|douro|seine|moselle|\bmain\b'),
 ('Caribbean', r'caribbean'),
 ('Mexico & Pacific Coast', r'mexican riviera|mexico|baja|cabo|pacific coast|california|west coast|ensenada|catalina'),
 ('Bahamas', r'bahamas|perfect day|cococay|ocean cay|great stirrup|getaway'),
 ('Caribbean', r'caribbean|aruba|curacao|cuba|jamaica|cayman|antilles|virgin islands|st\.? maarten|dominican|puerto rico'),
 ('Transatlantic & Repositioning', r'transatlantic|atlantic crossing|grand voyage|repositioning|transpacific|pacific crossing|world cruise|grand journey|crossing'),
]
PORTS = [  # (region, regex) scored by number of matching ports
 ('Alaska', r'alaska|juneau|skagway|ketchikan|sitka|seward|whittier|icy strait|hubbard|glacier|haines|endicott|dawes|tracy arm'),
 ('Hawaii', r'hawaii|honolulu|maui|kauai|kona|hilo|lahaina|nawiliwili|kahului'),
 ('Bermuda', r'bermuda|king.s wharf|royal naval dockyard'),
 ('Bahamas', r'bahamas|nassau|cococay|great stirrup|ocean cay|bimini|freeport|princess cays|half moon cay|celebration key'),
 ('Caribbean', r'cozumel|costa maya|roatan|belize|jamaica|falmouth|ocho rios|montego|cayman|george town|labadee|haiti|dominican|puerto plata|la romana|amber cove|san juan|puerto rico|st\.? thomas|charlotte amalie|st\.? croix|tortola|virgin|st\.? maarten|philipsburg|st\.? kitts|basseterre|antigua|st\.? john|st\.? lucia|castries|barbados|bridgetown|grenada|st\.? george|aruba|oranjestad|curacao|willemstad|bonaire|kralendijk|martinique|fort-de-france|guadeloupe|pointe-a-pitre|dominica|roseau|grand turk|turks|harvest caye|cartagena|colon|limon|samana|samaná|trinidad|tobago|st\.? vincent|bequia|nevis|anguilla|st\.? barth|santo domingo|progreso|puerto limon'),
 ('Mexico & Pacific Coast', r'cabo san lucas|mazatlan|mazatlán|puerto vallarta|ensenada|catalina|la paz|loreto|manzanillo|huatulco|acapulco|san diego|santa barbara|san francisco|astoria|monterey'),
 ('Canada & New England', r'halifax|saint john|sydney, nova|charlottetown|quebec|québec|bar harbor|portland, maine|boston|newport|saguenay|corner brook|st\. john.s|nova scotia|new brunswick|prince edward'),
 ('British Isles', r'ireland|scotland|england|wales|dublin|cork|cobh|belfast|glasgow|greenock|edinburgh|queensferry|invergordon|inverness|liverpool|kirkwall|orkney|lerwick|shetland|dover|portland, |holyhead|guernsey|st\. peter port|newcastle|stornoway|waterford|killybegs|falmouth, eng|isle of'),
 ('Northern Europe', r'norway|bergen|oslo|stavanger|geiranger|flam|flåm|alesund|ålesund|tromso|tromsø|honningsvag|olden|hellesylt|iceland|reykjavik|akureyri|isafjordur|denmark|copenhagen|aarhus|skagen|sweden|stockholm|gothenburg|visby|finland|helsinki|estonia|tallinn|latvia|riga|lithuania|klaipeda|poland|gdansk|gdynia|germany|hamburg|kiel|warnemunde|warnemünde|berlin|netherlands|amsterdam|rotterdam|belgium|zeebrugge|bruges|le havre|greenland|nuuk|faroe|torshavn|svalbard|longyearbyen|kristiansand|haugesund|molde|trondheim|nordfjordeid|maloy|eidfjord|cherbourg|southampton'),
 ('Mediterranean', r'italy|rome|civitavecchia|naples|genoa|venice|ravenna|trieste|livorno|florence|la spezia|messina|palermo|sicily|sardinia|cagliari|olbia|bari|brindisi|ancona|salerno|taranto|catania|portofino|spain|barcelona|valencia|palma|mallorca|ibiza|malaga|málaga|cartagena, spain|alicante|cadiz|cádiz|seville|tarragona|france|marseille|cannes|nice|villefranche|toulon|ajaccio|corsica|monaco|monte carlo|greece|athens|piraeus|mykonos|santorini|rhodes|corfu|crete|chania|heraklion|katakolon|kefalonia|argostoli|zakynthos|thessaloniki|volos|croatia|dubrovnik|split|zadar|montenegro|kotor|slovenia|koper|malta|valletta|turkey|istanbul|kusadasi|ephesus|izmir|bodrum|cyprus|limassol|israel|haifa|ashdod|egypt|alexandria|port said|tunisia|tunis|la goulette|portugal|lisbon|porto|gibraltar|albania|saranda'),
 ('Asia', r'japan|tokyo|yokohama|osaka|kobe|kyoto|nagasaki|hiroshima|fukuoka|hakodate|aomori|okinawa|naha|ishigaki|shimizu|kochi|kagoshima|korea|busan|jeju|seoul|incheon|china|shanghai|hong kong|tianjin|beijing|taiwan|taipei|keelung|kaohsiung|vietnam|ho chi minh|nha trang|da nang|ha long|thailand|bangkok|laem chabang|phuket|ko samui|singapore|malaysia|penang|kuala lumpur|port klang|langkawi|indonesia|bali|benoa|lombok|komodo|philippines|manila|boracay|india|mumbai|cochin|goa|sri lanka|colombo|cambodia|sihanoukville|brunei'),
 ('Australia & New Zealand', r'australia|sydney|melbourne|brisbane|hobart|adelaide|perth|fremantle|cairns|darwin|airlie|newcastle, aus|eden|kangaroo|port arthur|burnie|moreton|tasmania|new zealand|auckland|wellington|tauranga|napier|dunedin|port chalmers|akaroa|lyttelton|christchurch|picton|bay of islands|fiordland|milford'),
 ('South Pacific', r'fiji|suva|lautoka|vanuatu|port vila|mystery island|new caledonia|noumea|nouméa|lifou|isle of pines|tahiti|papeete|moorea|bora bora|raiatea|samoa|apia|pago pago|tonga|nuku|cook islands|rarotonga|french polynesia|conflict islands|papua'),
 ('Antarctica & South America', r'argentina|buenos aires|ushuaia|puerto madryn|uruguay|montevideo|punta del este|chile|valparaiso|san antonio, chile|punta arenas|puerto montt|brazil|rio de janeiro|santos|salvador|buzios|búzios|ilhabela|ilha grande|itajai|itajaí|balneario|angra|peru|lima|callao|ecuador|manta|falkland|stanley|antarctica|paradise bay|elephant island|cape horn|maceio|recife|fortaleza'),
 ('Galapagos', r'galapagos|baltra|santa cruz|isabela|fernandina|san cristobal|floreana|espanola|española|genovesa|santiago island|bartolome'),
 ('Middle East', r'dubai|abu dhabi|emirates|doha|qatar|bahrain|oman|muscat|khasab|salalah|saudi|jeddah|dammam|sir bani yas|aqaba|jordan|safaga'),
 ('Africa & Canary Islands', r'south africa|cape town|durban|port elizabeth|namibia|walvis|mozambique|maputo|madagascar|mauritius|port louis|reunion|réunion|seychelles|kenya|mombasa|zanzibar|tanzania|morocco|casablanca|tangier|agadir|canary|tenerife|las palmas|lanzarote|fuerteventura|la palma|madeira|funchal|cape verde|mindelo|senegal|dakar|pomene|portuguese island'),
]
NAME=[(r,re.compile(p,re.I)) for r,p in NAME]; PORTS=[(r,re.compile(p,re.I)) for r,p in PORTS]
def classify(r):
    name=r.get('itinerary') or ''
    stops=[r.get('departure_port') or '']+list(r.get('ports') or [])
    score=Counter()
    for s in stops:
        for reg,rx in PORTS:
            if rx.search(s): score[reg]+=1; break
    for reg,rx in NAME:
        if rx.search(name):
            if reg=='Transatlantic & Repositioning' or reg=='River Cruise': return reg
            if reg in ('Caribbean','Bahamas') and score.get('Caribbean',0)+score.get('Bahamas',0)==0 and score: break
            if reg=='Bahamas' and score.get('Caribbean',0)>score.get('Bahamas',0): return 'Caribbean'
            return reg
    if not score: return 'Other'
    top=score.most_common()
    if len(top)>1 and top[0][0]=='Bahamas' and 'Caribbean' in score: return 'Caribbean'
    regs=set(score)
    if (r.get('nights') or 0)>=10 and len(regs)>=3 and top[0][1]<=sum(score.values())/2: return 'Transatlantic & Repositioning'
    return top[0][0]
if __name__=='__main__':
    d=json.load(open(sys.argv[1],encoding='utf-8'))
    for r in d['sailings']: r['region']=classify(r)
    c=Counter(r['region'] for r in d['sailings']); print(c.most_common())
    oth=[r for r in d['sailings'] if r['region']=='Other']
    print(Counter((r['line'],r['itinerary'],r['departure_port']) for r in oth).most_common(25))
    if len(sys.argv)>2: json.dump(d,open(sys.argv[2],'w',encoding='utf-8'),separators=(',',':'),ensure_ascii=False)
