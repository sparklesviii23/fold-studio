"""Endpoint-specific summaries of explicitly declared experimental replicate units.

Only technical repeats are averaged first; a row is never silently counted as an
independent biological replicate. No affinity, dose-response or treatment fit.
"""
import collections
import math
import statistics

VERSION = 'biological-unit-summary-v1'
# scipy.stats.t.ppf(.975, df), SciPy 1.18.1; reference-tested, no runtime dependency.
T975 = (12.706204736174694,4.302652729749462,3.1824463052837078,2.7764451051977934,
        2.5705818356363146,2.446911851144979,2.364624251592784,2.306004135204166,
        2.262157162798205,2.228138851986274,2.2009851600916384,2.1788128296672284,
        2.1603686564627913,2.144786687917804,2.131449545559776,2.1199052992212546,
        2.1098155778333156,2.1009220402410382,2.0930240544083087,2.0859634472658644,
        2.0796138447276795,2.0738730679040254,2.0686576104190486,2.063898561628024,
        2.0595385527532977,2.0555294386428735,2.0518305164802846,2.048407141795245,
        2.045229642132704,2.0422724563012378)


def identifier(value, name):
    if not isinstance(value, str) or not value.strip() or len(value) > 100 or any(ord(c) < 32 for c in value):
        raise ValueError('Supply an explicit '+name+' identity of 1–100 characters without control characters.')
    return value.strip()


def explicit_rows(rows, endpoint, response_unit):
    if not isinstance(rows, list) or not 1 <= len(rows) <= 10000:
        raise ValueError('Supply 1–10,000 explicit measurement rows.')
    clean, seen = [], set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError('Each measurement must be an object.')
        if set(row)-{'concentration','response','biologicalReplicate','technicalReplicate','sampleGroup','endpoint','responseUnit'}:
            raise ValueError('Unsupported measurement field; endpoint and units must be explicit and consistent.')
        if row.get('endpoint', endpoint) != endpoint or row.get('responseUnit', response_unit) != response_unit:
            raise ValueError('Do not pool different endpoints or response units in one assay.')
        concentration, response = row.get('concentration'), row.get('response')
        if any(type(v) not in (int,float) or not math.isfinite(v) for v in (concentration,response)) or concentration < 0:
            raise ValueError('Measurements must be finite numbers with nonnegative concentration.')
        bio=identifier(row.get('biologicalReplicate'),'biological replicate')
        technical=identifier(row.get('technicalReplicate'),'technical replicate')
        group=identifier(row.get('sampleGroup'),'sample group / control')
        key=(group,concentration,bio,technical)
        if key in seen:
            raise ValueError('Duplicate group/dose/biological/technical identity; do not silently count a repeated reading twice.')
        seen.add(key)
        clean.append({'concentration':concentration,'response':response,'biologicalReplicate':bio,'technicalReplicate':technical,'sampleGroup':group})
    return clean


def summarize(assay):
    if assay.get('replicateDesign') != 'explicit_biological_technical':
        raise ValueError('Legacy replicate labels do not identify independent biological units. Save explicitly labelled biological and technical readings before computing this summary.')
    endpoint=identifier(assay.get('endpoint'),'measured endpoint')
    response_unit=identifier(assay.get('responseUnit'),'response unit')
    rows=explicit_rows(assay.get('rows'),endpoint,response_unit)
    units=collections.defaultdict(list)
    for row in rows:
        units[(row['sampleGroup'],row['concentration'],row['biologicalReplicate'])].append(row['response'])
    groups=collections.defaultdict(list)
    for (group,dose,bio),values in sorted(units.items()):
        groups[(group,dose)].append({'biologicalReplicate':bio,'technicalReadings':len(values),'mean':statistics.mean(values),
                                    'technicalSampleSD':statistics.stdev(values) if len(values)>1 else None})
    output=[]
    for (group,dose),biological in sorted(groups.items()):
        values=[unit['mean'] for unit in biological];n=len(values);mean=statistics.mean(values)
        sd=statistics.stdev(values) if n>1 else None
        sem=sd/math.sqrt(n) if sd is not None else None
        df=min(n-1,30) if n>1 else None
        half=T975[df-1]*sem if df else None
        if any(v is not None and not math.isfinite(v) for v in (mean,sd,sem,half)) or (half is not None and not all(math.isfinite(v) for v in (mean-half,mean+half))):
            raise ValueError('Measurement dispersion exceeds the finite numerical summary range.')
        output.append({'sampleGroup':group,'concentration':dose,'biologicalUnits':n,'rawReadings':sum(unit['technicalReadings'] for unit in biological),
                       'mean':mean,'sampleSD':sd,'standardError':sem,'confidenceInterval95':None if half is None else [mean-half,mean+half],
                       'intervalDegreesOfFreedom':df,'intervalIsConservative':n>31,'biologicalUnitSummaries':biological})
    return {'schemaVersion':1,'algorithm':VERSION,'endpoint':endpoint,'responseUnit':response_unit,'concentrationUnit':assay['concentrationUnit'],
            'groups':output,'totalRawReadings':len(rows),'method':'Within each group/dose, average technical readings per declared biological unit; give every biological unit equal weight. Sample SD uses n−1 and SEM uses biological n.',
            'intervalMethod':'Two-sided Student t 95% interval for the mean of independent, approximately normally distributed biological-unit means. Degrees of freedom are min(n−1,30); n>31 uses a conservative wider critical value. One biological unit has no estimated SD, SEM or confidence interval. Intervals are pointwise, not multiplicity-adjusted.',
            'limitations':['Biological-unit independence and endpoint/condition identity are supplied by the researcher, not verified from the readings.','Repeated doses from the same biological units are correlated; no across-dose/group hypothesis test or dose-response/affinity fit is performed.','Technical repeats do not increase the inferential biological sample size. Descriptive intervals do not establish efficacy, binding, causality or experimental validity.']}
