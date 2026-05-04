'use client';

import React, { useState } from 'react';
import Link from 'next/link';

// Design tokens
const ST = {
  bg: '#f6f7fb',
  bgDeep: '#eef0f7',
  panel: '#ffffff',
  panel2: '#fafbfd',
  border: 'rgba(15,18,40,0.08)',
  border2: 'rgba(15,18,40,0.14)',
  divider: 'rgba(15,18,40,0.06)',
  ink: '#0c1030',
  ink2: 'rgba(12,16,48,0.82)',
  ink3: 'rgba(12,16,48,0.58)',
  ink4: 'rgba(12,16,48,0.40)',
  ink5: 'rgba(12,16,48,0.22)',
  brand: '#5B6CFF',
  brand2: '#4754E8',
  brand3: '#7F60E8',
  brandTint: 'rgba(91,108,255,0.08)',
  brandTint2: 'rgba(91,108,255,0.14)',
};

const TRIG = {
  funding: '#16a34a',
  leadership: '#2e6dd9',
  expansion: '#ca8a04',
  hiring: '#7c3aed',
  product: '#db2777',
  velocity: '#ea580c',
  distress: '#dc2626',
};

function heatST(pct: number) {
  if (pct >= 90) return { main: '#2e6dd9', tier: 'Closest match', ring: 'rgba(46,109,217,0.22)' };
  if (pct >= 75) return { main: '#16a34a', tier: 'Strong match', ring: 'rgba(22,163,74,0.22)' };
  if (pct >= 60) return { main: '#ca8a04', tier: 'Medium match', ring: 'rgba(202,138,4,0.22)' };
  if (pct >= 45) return { main: '#dc6d18', tier: 'Partial match', ring: 'rgba(220,109,24,0.22)' };
  return { main: '#dc2626', tier: 'Weak match', ring: 'rgba(220,38,38,0.22)' };
}

// ============================================================================
// TYPE DEFINITIONS
// ============================================================================

interface Vacancy {
  id: number;
  role: string;
  company: string;
  logo: string;
  color: string;
  match: number;
  salary: string;
  equity: string;
  mode: string;
  posted: string;
  source: string;
  fit: string[];
}

interface Prediction {
  co: string;
  logo: string;
  color: string;
  role: string;
  conf: number;
  when: string;
  trig: keyof typeof TRIG;
  trigLabel: string;
  basis: string;
  history: Array<{ at: string; txt: string }>;
}

interface Signal {
  id: number;
  lead?: boolean;
  headline: string;
  excerpt: string;
  source: string;
  byline: string;
  when: string;
  trig: keyof typeof TRIG;
  co: string;
  logo: string;
  color: string;
  impact: string;
  related?: string[];
}

interface Gig {
  id: number;
  title: string;
  client: string;
  logoBg: string;
  logo: string;
  marketplace: string;
  fit: number;
  rate: string;
  commitment: string;
  duration: string;
  focus: string[];
  status: 'hot' | 'new' | '';
  posted: string;
  blurb: string;
}

// ============================================================================
// MOCK DATA
// ============================================================================

const VACANCIES: Vacancy[] = [
  {
    id: 1,
    role: 'Head of Product',
    company: 'Linear',
    logo: 'L',
    color: '#5E6AD2',
    match: 94,
    salary: '$240–$290k',
    equity: '0.20–0.40%',
    mode: 'Remote',
    posted: '2h ago',
    source: 'Greenhouse',
    fit: ['Led 4-PM team', 'B2B SaaS depth', 'Series C exp.'],
  },
  {
    id: 2,
    role: 'Sr. Product Manager',
    company: 'Vercel',
    logo: '▲',
    color: '#0a0a0a',
    match: 88,
    salary: '$210–$260k',
    equity: '0.08–0.15%',
    mode: 'Hybrid · NYC',
    posted: '1d ago',
    source: 'Lever',
    fit: ['DevTools experience', 'Growth PM history'],
  },
  {
    id: 3,
    role: 'Director of Product',
    company: 'Ramp',
    logo: 'R',
    color: '#FFB800',
    match: 81,
    salary: '$260–$310k',
    equity: '0.15–0.30%',
    mode: 'NYC',
    posted: '2d ago',
    source: 'Greenhouse',
    fit: ['Fintech adjacent', 'Director-level scope'],
  },
  {
    id: 4,
    role: 'Group Product Manager',
    company: 'Notion',
    logo: 'N',
    color: '#0a0a0a',
    match: 76,
    salary: '$220–$270k',
    equity: '0.06–0.12%',
    mode: 'Remote',
    posted: '3d ago',
    source: 'Workday',
    fit: ['Collab tool background', 'GPM scope match'],
  },
  {
    id: 5,
    role: 'Principal PM, Platform',
    company: 'Figma',
    logo: 'F',
    color: '#F24E1E',
    match: 68,
    salary: '$250–$300k',
    equity: '0.10–0.20%',
    mode: 'SF',
    posted: '4d ago',
    source: 'Greenhouse',
    fit: ['Platform PM stretch', 'Design tools ecosystem'],
  },
  {
    id: 6,
    role: 'Senior PM, Growth',
    company: 'Stripe',
    logo: 'S',
    color: '#635BFF',
    match: 62,
    salary: '$215–$255k',
    equity: '0.05–0.10%',
    mode: 'Hybrid · SF',
    posted: '5d ago',
    source: 'Lever',
    fit: ['Growth motions', 'Activation funnels'],
  },
  {
    id: 7,
    role: 'Lead PM, Infra',
    company: 'Anthropic',
    logo: 'A',
    color: '#D97757',
    match: 48,
    salary: '$240–$290k',
    equity: 'variable',
    mode: 'SF',
    posted: '6d ago',
    source: 'Ashby',
    fit: ['AI-curious', 'Infra is a stretch'],
  },
  {
    id: 8,
    role: 'Sr. PM, Payments',
    company: 'Plaid',
    logo: 'P',
    color: '#0a0a0a',
    match: 79,
    salary: '$220–$265k',
    equity: '0.08–0.14%',
    mode: 'Remote',
    posted: '6h ago',
    source: 'Greenhouse',
    fit: ['API products', 'Fintech rails'],
  },
  {
    id: 9,
    role: 'Senior PM, Editor',
    company: 'Linear',
    logo: 'L',
    color: '#5E6AD2',
    match: 72,
    salary: '$200–$240k',
    equity: '0.06–0.10%',
    mode: 'Remote',
    posted: '3h ago',
    source: 'Greenhouse',
    fit: ['Editor surfaces', 'Pro-grade UX'],
  },
];

const PREDICTIONS: Prediction[] = [
  {
    co: 'Plaid',
    logo: 'P',
    color: '#0a0a0a',
    role: 'VP of Product',
    conf: 88,
    when: 'Within 90 days',
    trig: 'leadership',
    trigLabel: 'Sandeep V., VP Product, departed Apr 18 (LinkedIn)',
    basis: '3 of last 4 VP-level exits at Plaid backfilled within 75 days.',
    history: [
      { at: 'Apr 18', txt: 'Sandeep V. announces departure on LinkedIn' },
      { at: 'Apr 19', txt: '4 Plaid PMs update profiles (passive signal)' },
      { at: 'Apr 21', txt: "Recruiter screen spotted for 'senior product leader'" },
      { at: 'Today', txt: 'Scout confidence raised to 88%' },
    ],
  },
  {
    co: 'Linear',
    logo: 'L',
    color: '#5E6AD2',
    role: 'Director of Design',
    conf: 74,
    when: '30–60 days',
    trig: 'funding',
    trigLabel: '$80M Series C announced Apr 20, co-led Sequoia + Accel',
    basis: 'Pattern match: design leadership hire follows every Series C in dev-tools (Figma, Notion, Vercel).',
    history: [
      { at: 'Apr 20', txt: '$80M Series C announced' },
      { at: 'Apr 22', txt: '3 design roles posted on Greenhouse' },
      { at: 'Today', txt: 'Director-level gap in org chart confirmed' },
    ],
  },
  {
    co: 'Vercel',
    logo: '▲',
    color: '#0a0a0a',
    role: 'Head of Growth',
    conf: 69,
    when: '60–90 days',
    trig: 'expansion',
    trigLabel: 'NYC HQ floor 14 lease signed (SEC filing Mar 28)',
    basis: 'Real-estate signal + no current Head of Growth = 69% probability of hire.',
    history: [
      { at: 'Mar 28', txt: 'Floor 14 lease signed (SEC filing)' },
      { at: 'Apr 10', txt: 'Growth PM role posted (likely advance team)' },
      { at: 'Today', txt: 'No Head of Growth in org chart → gap flagged' },
    ],
  },
  {
    co: 'Notion',
    logo: 'N',
    color: '#0a0a0a',
    role: 'GPM, AI',
    conf: 62,
    when: '60–90 days',
    trig: 'product',
    trigLabel: 'Notion AI 3.0 launched Apr 15 — 1.2M WAU in first week',
    basis: 'Product launch + hiring surge pattern. 62% confidence a GPM-level role forms.',
    history: [
      { at: 'Apr 15', txt: 'Notion AI 3.0 ships' },
      { at: 'Apr 18', txt: '1.2M WAU reported (internal leak)' },
      { at: 'Today', txt: 'PM headcount on AI team doubled in 6mo' },
    ],
  },
  {
    co: 'Stripe',
    logo: 'S',
    color: '#635BFF',
    role: 'Sr. PM, Atlas',
    conf: 58,
    when: 'Q3 2026',
    trig: 'velocity',
    trigLabel: 'Atlas team grew 32% in 90 days (LinkedIn headcount)',
    basis: 'Team velocity outpaces current PM coverage. 58% confidence another PM forms in Q3.',
    history: [
      { at: 'Feb', txt: 'Atlas team at 18 eng' },
      { at: 'Mar', txt: '24 eng (6 hires in 30d)' },
      { at: 'Today', txt: '1 PM covers 24 eng → ratio suggests hire' },
    ],
  },
];

const SIGNALS: Signal[] = [
  {
    id: 1,
    lead: true,
    headline: 'Stripe raises $5B Series I at $91B valuation',
    excerpt: 'The fintech giant confirmed today...',
    source: 'TechCrunch',
    byline: 'Mary Ann Azevedo',
    when: '6h ago',
    trig: 'funding',
    co: 'Stripe',
    logo: 'S',
    color: '#635BFF',
    impact: '+8 likely product roles in the next 90 days. Atlas and Billing teams flagged for expansion.',
    related: [
      'Stripe job postings jumped 14% this week',
      "Bill Wurth (CPO) posted about 'building the next wave'",
      'Stripe\'s careers site added 3 unlisted PM roles',
    ],
  },
  {
    id: 2,
    headline: 'Linear hires Sarah Tavel as first CPO',
    excerpt: 'Tavel, formerly partner at Benchmark, joins as Linear\'s first Chief Product Officer.',
    source: 'The Information',
    byline: 'Cory Weinberg',
    when: 'yesterday',
    trig: 'leadership',
    co: 'Linear',
    logo: 'L',
    color: '#5E6AD2',
    impact: 'Backfill 3–5 PM roles expected as Tavel restructures product org.',
  },
  {
    id: 3,
    headline: 'Ramp leases floors 21–22 at 3 WTC, NYC',
    excerpt: 'The corporate card startup is doubling its NYC footprint...',
    source: 'Commercial Observer',
    byline: 'Mark Hallum',
    when: '2d ago',
    trig: 'expansion',
    co: 'Ramp',
    logo: 'R',
    color: '#FFB800',
    impact: 'NYC hiring wave likely. Product and engineering roles expected within 60d.',
  },
  {
    id: 4,
    headline: 'Figma ships Dev Mode 2.0 to 800k teams',
    excerpt: 'Major product bet lands. Dev Mode now auto-generates code specs...',
    source: 'The Verge',
    byline: 'Adi Robertson',
    when: '2d ago',
    trig: 'product',
    co: 'Figma',
    logo: 'F',
    color: '#F24E1E',
    impact: 'Dev Mode team likely hiring 2–3 PMs to scale the new surface.',
  },
  {
    id: 5,
    headline: 'Notion AI passes 2M weekly active users',
    excerpt: 'After a slower-than-expected start, Notion\'s AI features hit escape velocity.',
    source: 'The Information',
    byline: 'Kate Clark',
    when: '3d ago',
    trig: 'velocity',
    co: 'Notion',
    logo: 'N',
    color: '#0a0a0a',
    impact: 'AI team PM headcount doubled in 6mo. Further hires likely.',
  },
  {
    id: 6,
    headline: 'Plaid VP of Product Sandeep Verma departs',
    excerpt: 'Verma, who led Plaid\'s core API platform...',
    source: 'LinkedIn',
    byline: 'Sandeep Verma (post)',
    when: '4d ago',
    trig: 'leadership',
    co: 'Plaid',
    logo: 'P',
    color: '#0a0a0a',
    impact: 'Backfill VP role expected within 90 days. Search likely underway.',
  },
  {
    id: 7,
    headline: 'Mercury raises $300M Series C',
    excerpt: 'The startup banking platform led by Immad Akhund...',
    source: 'TechCrunch',
    byline: 'Mary Ann Azevedo',
    when: '5d ago',
    trig: 'funding',
    co: 'Mercury',
    logo: 'M',
    color: '#22c55e',
    impact: 'Consumer banking line forming. PM + growth hires expected.',
  },
  {
    id: 8,
    headline: 'Anthropic engineering headcount +40% in 90 days',
    excerpt: 'Per LinkedIn data, Anthropic\'s engineering org grew from 310 to 434...',
    source: 'Scout · internal',
    byline: 'automated',
    when: 'this week',
    trig: 'velocity',
    co: 'Anthropic',
    logo: 'A',
    color: '#D97757',
    impact: 'Product team likely expanding in parallel. Infra PM roles probable.',
  },
];

const GIGS: Gig[] = [
  {
    id: 1,
    title: 'Fractional Head of Product',
    client: 'Series B SaaS · 80 ppl',
    logoBg: '#0c1030',
    logo: 'S2',
    marketplace: 'A.Team',
    fit: 91,
    rate: '$1,400/day',
    commitment: '3 days/wk',
    duration: '6 mo',
    focus: ['Product strategy', 'B2B SaaS', 'Roadmap'],
    status: 'hot',
    posted: '2h ago',
    blurb: 'Profitable Series B fintech building next-gen expense management.',
  },
  {
    id: 2,
    title: 'Senior PM, AI Product Strategy',
    client: 'Stealth · pre-seed',
    logoBg: '#5E6AD2',
    logo: 'ST',
    marketplace: 'Toptal',
    fit: 84,
    rate: '$200/hr',
    commitment: '20 hrs/wk',
    duration: '3 mo',
    focus: ['AI/ML', '0→1', 'Strategy'],
    status: 'new',
    posted: '5h ago',
    blurb: 'Two-time founder, ex-OpenAI researcher, building AI compliance tool.',
  },
  {
    id: 3,
    title: 'Product Advisor, Growth',
    client: 'EdTech · Series A · 40 ppl',
    logoBg: '#16a34a',
    logo: 'ED',
    marketplace: 'Catalant',
    fit: 76,
    rate: '$1,100/day',
    commitment: '2 days/wk',
    duration: '3 mo',
    focus: ['Growth', 'Activation', 'B2C'],
    status: '',
    posted: '1d ago',
    blurb: 'EdTech company needs growth PM to fix onboarding funnel.',
  },
  {
    id: 4,
    title: 'Interim VP Product',
    client: 'HealthTech · Series B',
    logoBg: '#dc2626',
    logo: 'HT',
    marketplace: 'A.Team',
    fit: 82,
    rate: '$1,800/day',
    commitment: '4 days/wk',
    duration: '4 mo',
    focus: ['Leadership', 'HealthTech', 'Team building'],
    status: 'hot',
    posted: '3h ago',
    blurb: 'VP departed suddenly. Need interim leader while they search.',
  },
  {
    id: 5,
    title: 'Product Strategy Consultant',
    client: 'Enterprise SaaS · 200 ppl',
    logoBg: '#ca8a04',
    logo: 'ES',
    marketplace: 'Braintrust',
    fit: 69,
    rate: '$950/day',
    commitment: '2 days/wk',
    duration: '2 mo',
    focus: ['Enterprise', 'Pricing', 'GTM'],
    status: '',
    posted: '2d ago',
    blurb: 'Pricing and packaging review for enterprise SaaS platform.',
  },
  {
    id: 6,
    title: 'Fractional CPO',
    client: 'FinTech · Seed · 12 ppl',
    logoBg: '#635BFF',
    logo: 'FN',
    marketplace: 'Toptal',
    fit: 88,
    rate: '$1,600/day',
    commitment: '3 days/wk',
    duration: '6 mo',
    focus: ['0→1', 'Fintech', 'Fundraising support'],
    status: 'new',
    posted: '8h ago',
    blurb: 'Seed-stage fintech needs product leader to get to Series A.',
  },
];

const MARKETS = [
  { id: 'toptal', label: 'Toptal', count: 5, color: '#3863F0' },
  { id: 'ateam', label: 'A.Team', count: 4, color: '#0c1030' },
  { id: 'catalant', label: 'Catalant', count: 3, color: '#ea580c' },
  { id: 'braintrust', label: 'Braintrust', count: 2, color: '#16a34a' },
];

// ============================================================================
// COMPONENTS
// ============================================================================

function MatchGauge({ pct }: { pct: number }) {
  const h = heatST(pct);
  const circumference = 2 * Math.PI * 27;
  const dasharray = (pct / 100) * circumference;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
      <svg width="64" height="64" viewBox="0 0 64 64" style={{ display: 'block' }}>
        <circle cx="32" cy="32" r="27" stroke={ST.border} strokeWidth="4" fill="none" />
        <circle
          cx="32"
          cy="32"
          r="27"
          stroke={h.main}
          strokeWidth="4"
          fill="none"
          strokeDasharray={`${dasharray} ${circumference}`}
          strokeLinecap="round"
          style={{ transform: 'rotate(-90deg)', transformOrigin: '32px 32px' }}
        />
        <text
          x="32"
          y="35"
          textAnchor="middle"
          fontSize="17"
          fontWeight="700"
          fill={h.main}
          fontFamily="'JetBrains Mono', monospace"
        >
          {pct}%
        </text>
      </svg>
      <div
        style={{
          marginTop: '6px',
          fontSize: '7px',
          color: h.main,
          textTransform: 'uppercase',
          fontWeight: '600',
          letterSpacing: '0.5px',
        }}
      >
        {h.tier}
      </div>
    </div>
  );
}

function VacancyCard({ vacancy }: { vacancy: Vacancy }) {
  const h = heatST(vacancy.match);

  return (
    <div
      style={{
        background: ST.panel,
        border: `1px solid ${ST.border}`,
        borderRadius: '12px',
        padding: '16px',
        display: 'grid',
        gridTemplateColumns: '68px 44px 1fr 200px 150px',
        gap: '14px',
        alignItems: 'center',
        boxShadow: '0 1px 2px rgba(0,0,0,0.04)',
      }}
    >
      {/* Column 1: Match gauge */}
      <MatchGauge pct={vacancy.match} />

      {/* Column 2: Logo */}
      <div
        style={{
          width: '40px',
          height: '40px',
          borderRadius: '7px',
          background: vacancy.color,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: '#ffffff',
          fontSize: `${40 * 0.42}px`,
          fontWeight: '700',
          boxShadow: '0 1px 2px rgba(15,18,40,0.10)',
        }}
      >
        {vacancy.logo}
      </div>

      {/* Column 3: Role info */}
      <div>
        <div style={{ fontSize: '16px', fontWeight: '600', letterSpacing: '-0.2px', color: ST.ink }}>
          {vacancy.role}
        </div>
        <div style={{ fontSize: '13px', color: ST.ink3, fontWeight: '500' }}>{vacancy.company}</div>
        <div
          style={{
            fontSize: '9px',
            padding: '2px 7px',
            borderRadius: '4px',
            border: `1px solid ${h.ring}`,
            color: h.main,
            fontWeight: '600',
            textTransform: 'uppercase',
            display: 'inline-block',
            marginTop: '4px',
          }}
        >
          {h.tier}
        </div>

        {/* Meta row */}
        <div
          style={{
            display: 'flex',
            gap: '10px',
            fontSize: '12px',
            color: ST.ink3,
            marginTop: '6px',
            flexWrap: 'wrap',
          }}
        >
          <span style={{ color: ST.ink2, fontWeight: '500' }}>{vacancy.salary}</span>
          <span>•</span>
          <span>{vacancy.equity} equity</span>
          <span>•</span>
          <span>{vacancy.mode}</span>
          <span>•</span>
          <span>{vacancy.posted}</span>
          <span>•</span>
          <span>{vacancy.source}</span>
        </div>

        {/* Fit tags */}
        <div style={{ display: 'flex', gap: '5px', marginTop: '6px', flexWrap: 'wrap' }}>
          {vacancy.fit.map((tag, i) => (
            <span
              key={i}
              style={{
                fontSize: '10.5px',
                padding: '2px 8px',
                borderRadius: '5px',
                background: ST.brandTint,
                color: ST.brand2,
                fontWeight: '500',
              }}
            >
              {tag}
            </span>
          ))}
        </div>
      </div>

      {/* Column 4: Why it matches */}
      <div>
        <div
          style={{
            fontSize: '9px',
            color: ST.ink4,
            textTransform: 'uppercase',
            letterSpacing: '0.7px',
            fontWeight: '600',
            marginBottom: '4px',
          }}
        >
          WHY
        </div>
        <div style={{ fontSize: '11px', color: ST.ink3, lineHeight: '1.5' }}>
          Strongest fit: led {vacancy.company} transition from Lean to Agile. Your depth matches Series {vacancy.company.length > 5 ? 'C' : 'B'} execution.
        </div>
      </div>

      {/* Column 5: Actions */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
        <button
          style={{
            padding: '8px 12px',
            borderRadius: '8px',
            background: `linear-gradient(135deg, ${ST.brand} 0%, ${ST.brand2} 100%)`,
            fontSize: '12px',
            fontWeight: '600',
            color: '#ffffff',
            border: 'none',
            cursor: 'pointer',
            boxShadow: '0 2px 8px rgba(91,108,255,0.20)',
          }}
        >
          View role
        </button>
        <button
          style={{
            padding: '7px 10px',
            borderRadius: '7px',
            background: ST.panel,
            border: `1px solid ${ST.border2}`,
            fontSize: '11px',
            color: ST.ink2,
            fontWeight: '500',
            cursor: 'pointer',
          }}
        >
          Save
        </button>
      </div>
    </div>
  );
}

function TriggerChip({ trigger }: { trigger: keyof typeof TRIG }) {
  const triggerLabels: { [key in keyof typeof TRIG]: string } = {
    funding: 'Funding',
    leadership: 'Leadership',
    expansion: 'Expansion',
    hiring: 'Hiring',
    product: 'Product',
    velocity: 'Velocity',
    distress: 'Distress',
  };

  return (
    <div
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: '6px',
        padding: '3px 8px',
        borderRadius: '4px',
        background: `${TRIG[trigger]}22`,
        fontSize: '10px',
        fontWeight: '600',
        color: TRIG[trigger],
        textTransform: 'uppercase',
        letterSpacing: '0.3px',
      }}
    >
      <span
        style={{
          width: '6px',
          height: '6px',
          borderRadius: '50%',
          background: TRIG[trigger],
        }}
      />
      {triggerLabels[trigger]}
    </div>
  );
}

function PredictionCard({ pred }: { pred: Prediction }) {
  return (
    <div style={{ background: ST.panel, borderRadius: '12px', overflow: 'hidden', border: `1px solid ${ST.border}` }}>
      {/* Row 1: Header */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: '56px 1fr 220px 160px',
          gap: '16px',
          padding: '16px 18px',
          alignItems: 'center',
        }}
      >
        {/* Logo */}
        <div
          style={{
            width: '48px',
            height: '48px',
            borderRadius: '8px',
            background: pred.color,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#ffffff',
            fontSize: '18px',
            fontWeight: '700',
          }}
        >
          {pred.logo}
        </div>

        {/* Role info */}
        <div>
          <div style={{ display: 'flex', gap: '8px', marginBottom: '4px', alignItems: 'center' }}>
            <span
              style={{
                fontSize: '8px',
                padding: '2px 6px',
                background: ST.brandTint,
                color: ST.brand2,
                borderRadius: '3px',
                fontWeight: '600',
                textTransform: 'uppercase',
              }}
            >
              Predicted
            </span>
            <TriggerChip trigger={pred.trig} />
          </div>
          <div style={{ fontSize: '13px', color: ST.ink3, fontWeight: '500' }}>{pred.co}</div>
          <div style={{ fontSize: '18px', fontWeight: '600', color: ST.ink, letterSpacing: '-0.3px' }}>
            {pred.role}
          </div>
          <div style={{ fontSize: '11px', color: ST.ink3, marginTop: '2px' }}>{pred.when}</div>
        </div>

        {/* Confidence */}
        <div>
          <div
            style={{
              fontSize: '26px',
              fontWeight: '700',
              color: ST.brand,
              fontVariantNumeric: 'tabular-nums',
            }}
          >
            {pred.conf}%
          </div>
          <div
            style={{
              height: '4px',
              background: ST.bgDeep,
              borderRadius: '2px',
              overflow: 'hidden',
              marginTop: '4px',
            }}
          >
            <div
              style={{
                height: '100%',
                background: ST.brand,
                width: `${pred.conf}%`,
              }}
            />
          </div>
        </div>

        {/* Actions */}
        <div style={{ display: 'flex', gap: '6px', flexDirection: 'column' }}>
          <button
            style={{
              padding: '6px 10px',
              borderRadius: '6px',
              background: `linear-gradient(135deg, ${ST.brand} 0%, ${ST.brand2} 100%)`,
              fontSize: '11px',
              fontWeight: '600',
              color: '#ffffff',
              border: 'none',
              cursor: 'pointer',
            }}
          >
            Watch
          </button>
        </div>
      </div>

      {/* Row 2: Trigger + Basis */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: '1fr 1fr',
          borderTop: `1px solid ${ST.divider}`,
          background: ST.panel2,
        }}
      >
        <div style={{ padding: '12px 18px', borderRight: `1px solid ${ST.divider}` }}>
          <div style={{ fontSize: '8.5px', color: ST.ink4, textTransform: 'uppercase', fontWeight: '600', letterSpacing: '0.5px', marginBottom: '4px' }}>
            Trigger
          </div>
          <div style={{ fontSize: '11px', color: ST.ink2, lineHeight: '1.4' }}>{pred.trigLabel}</div>
        </div>
        <div style={{ padding: '12px 18px' }}>
          <div style={{ fontSize: '8.5px', color: ST.ink4, textTransform: 'uppercase', fontWeight: '600', letterSpacing: '0.5px', marginBottom: '4px' }}>
            Basis
          </div>
          <div style={{ fontSize: '11px', color: ST.ink2, lineHeight: '1.4' }}>{pred.basis}</div>
        </div>
      </div>

      {/* Row 3: Signal timeline */}
      <div style={{ borderTop: `1px solid ${ST.divider}`, padding: '12px 18px', background: ST.panel }}>
        <div
          style={{
            fontSize: '8.5px',
            color: ST.ink4,
            textTransform: 'uppercase',
            fontWeight: '600',
            letterSpacing: '0.5px',
            marginBottom: '8px',
          }}
        >
          Signal Timeline
        </div>
        <div style={{ display: 'flex', gap: '16px', overflowX: 'auto' }}>
          {pred.history.map((event, i) => (
            <div key={i} style={{ display: 'flex', gap: '8px', alignItems: 'flex-start', minWidth: 'fit-content' }}>
              <div
                style={{
                  width: '8px',
                  height: '8px',
                  borderRadius: '50%',
                  background: ST.brand,
                  marginTop: '2px',
                  flexShrink: 0,
                }}
              />
              <div>
                <div style={{ fontSize: '9px', color: ST.ink4, fontWeight: '600', whiteSpace: 'nowrap' }}>{event.at}</div>
                <div style={{ fontSize: '10px', color: ST.ink3, marginTop: '1px', maxWidth: '140px' }}>{event.txt}</div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function SignalCard({ signal, isLead }: { signal: Signal; isLead?: boolean }) {
  if (isLead) {
    return (
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: '1fr 280px',
          gap: '28px',
          padding: '24px',
          background: ST.panel,
          border: `1px solid ${ST.border}`,
          borderRadius: '14px',
        }}
      >
        {/* Left: Content */}
        <div>
          <div style={{ display: 'flex', gap: '10px', marginBottom: '12px', alignItems: 'center', flexWrap: 'wrap' }}>
            <span
              style={{
                fontSize: '8px',
                padding: '3px 8px',
                background: ST.brandTint,
                color: ST.brand2,
                borderRadius: '4px',
                fontWeight: '700',
                textTransform: 'uppercase',
                letterSpacing: '0.4px',
              }}
            >
              Lead Story
            </span>
            <TriggerChip trigger={signal.trig} />
            <span
              style={{
                fontSize: '8px',
                padding: '3px 8px',
                background: '#fef08a',
                color: '#854d0e',
                borderRadius: '4px',
                fontWeight: '700',
                textTransform: 'uppercase',
                letterSpacing: '0.4px',
              }}
            >
              High Impact
            </span>
          </div>

          <h2
            style={{
              fontSize: '30px',
              fontWeight: '700',
              letterSpacing: '-1px',
              color: ST.ink,
              marginBottom: '12px',
              margin: '0 0 12px 0',
            }}
          >
            {signal.headline}
          </h2>

          <div
            style={{
              fontSize: '13px',
              color: ST.ink3,
              marginBottom: '16px',
              display: 'flex',
              gap: '8px',
              flexWrap: 'wrap',
            }}
          >
            <span style={{ fontWeight: '600' }}>{signal.source}</span>
            <span>·</span>
            <span>{signal.byline}</span>
            <span>·</span>
            <span>{signal.when}</span>
          </div>

          <p style={{ fontSize: '14px', color: ST.ink2, lineHeight: '1.5', marginBottom: '18px', margin: '0 0 18px 0' }}>
            {signal.excerpt}
          </p>

          {/* Impact box */}
          <div
            style={{
              padding: '14px 16px',
              background: ST.brandTint,
              borderLeft: `3px solid ${ST.brand}`,
              borderRadius: '6px',
              fontSize: '12px',
              color: ST.ink2,
              lineHeight: '1.5',
            }}
          >
            <strong>Impact:</strong> {signal.impact}
          </div>

          {/* Related observations */}
          {signal.related && signal.related.length > 0 && (
            <div style={{ marginTop: '16px' }}>
              <div
                style={{
                  fontSize: '9px',
                  color: ST.ink4,
                  textTransform: 'uppercase',
                  fontWeight: '600',
                  letterSpacing: '0.5px',
                  marginBottom: '8px',
                }}
              >
                Related Observations
              </div>
              <ul
                style={{
                  listStyle: 'none',
                  padding: 0,
                  margin: 0,
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '6px',
                }}
              >
                {signal.related.map((obs, i) => (
                  <li key={i} style={{ fontSize: '11px', color: ST.ink3, paddingLeft: '16px', position: 'relative' }}>
                    <span style={{ position: 'absolute', left: 0 }}>•</span>
                    {obs}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>

        {/* Right: Logo + actions */}
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '16px' }}>
          <div
            style={{
              width: '88px',
              height: '88px',
              borderRadius: '12px',
              background: signal.color,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#ffffff',
              fontSize: '42px',
              fontWeight: '700',
            }}
          >
            {signal.logo}
          </div>
          <button
            style={{
              padding: '10px 16px',
              borderRadius: '8px',
              background: `linear-gradient(135deg, ${ST.brand} 0%, ${ST.brand2} 100%)`,
              fontSize: '12px',
              fontWeight: '600',
              color: '#ffffff',
              border: 'none',
              cursor: 'pointer',
            }}
          >
            Read more
          </button>
          <button
            style={{
              padding: '8px 12px',
              borderRadius: '6px',
              background: ST.panel2,
              border: `1px solid ${ST.border2}`,
              fontSize: '11px',
              color: ST.ink2,
              fontWeight: '500',
              cursor: 'pointer',
            }}
          >
            Save
          </button>
        </div>
      </div>
    );
  }

  // Regular signal card
  return (
    <div
      style={{
        background: ST.panel,
        border: `1px solid ${ST.border}`,
        borderRadius: '12px',
        overflow: 'hidden',
      }}
    >
      {/* Header */}
      <div
        style={{
          padding: '12px 16px',
          display: 'flex',
          gap: '10px',
          alignItems: 'center',
          borderBottom: `1px solid ${ST.divider}`,
        }}
      >
        <div
          style={{
            width: '32px',
            height: '32px',
            borderRadius: '6px',
            background: signal.color,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#ffffff',
            fontSize: '13px',
            fontWeight: '700',
            flexShrink: 0,
          }}
        >
          {signal.logo}
        </div>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: '10px', color: ST.ink4, fontWeight: '600' }}>{signal.source}</div>
          <div style={{ fontSize: '10px', color: ST.ink3 }}>{signal.when}</div>
        </div>
        <TriggerChip trigger={signal.trig} />
      </div>

      {/* Body */}
      <div style={{ padding: '12px 16px' }}>
        <h3
          style={{
            fontSize: '14px',
            fontWeight: '600',
            color: ST.ink,
            marginBottom: '6px',
            lineHeight: '1.4',
            margin: '0 0 6px 0',
          }}
        >
          {signal.headline}
        </h3>
        <p
          style={{
            fontSize: '12px',
            color: ST.ink3,
            lineHeight: '1.4',
            marginBottom: '10px',
            display: '-webkit-box',
            WebkitLineClamp: 3,
            WebkitBoxOrient: 'vertical',
            overflow: 'hidden',
            margin: '0 0 10px 0',
          }}
        >
          {signal.excerpt}
        </p>

        {/* Impact box */}
        <div
          style={{
            padding: '8px 10px',
            background: ST.brandTint,
            borderLeft: `3px solid ${ST.brand}`,
            borderRadius: '4px',
            fontSize: '10px',
            color: ST.ink3,
            lineHeight: '1.4',
            marginBottom: '10px',
          }}
        >
          {signal.impact}
        </div>

        {/* Actions */}
        <div style={{ display: 'flex', gap: '6px' }}>
          <button
            style={{
              flex: 1,
              padding: '6px 10px',
              borderRadius: '6px',
              background: `linear-gradient(135deg, ${ST.brand} 0%, ${ST.brand2} 100%)`,
              fontSize: '11px',
              fontWeight: '600',
              color: '#ffffff',
              border: 'none',
              cursor: 'pointer',
            }}
          >
            Read
          </button>
          <button
            style={{
              flex: 1,
              padding: '6px 10px',
              borderRadius: '6px',
              background: ST.panel2,
              border: `1px solid ${ST.border2}`,
              fontSize: '11px',
              color: ST.ink2,
              fontWeight: '500',
              cursor: 'pointer',
            }}
          >
            Save
          </button>
        </div>
      </div>
    </div>
  );
}

function GigCard({ gig }: { gig: Gig }) {
  return (
    <div
      style={{
        background: ST.panel,
        border: `1px solid ${ST.border}`,
        borderRadius: '12px',
        overflow: 'hidden',
        position: 'relative',
      }}
    >
      {/* Status badge */}
      {gig.status && (
        <div
          style={{
            position: 'absolute',
            top: '12px',
            right: '12px',
            fontSize: '8px',
            padding: '3px 8px',
            borderRadius: '3px',
            fontWeight: '700',
            textTransform: 'uppercase',
            letterSpacing: '0.4px',
            background: gig.status === 'hot' ? '#fecaca' : '#bfdbfe',
            color: gig.status === 'hot' ? '#991b1b' : '#1e3a8a',
            zIndex: 1,
          }}
        >
          {gig.status}
        </div>
      )}

      {/* Header row */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: '54px 1fr 130px 130px 140px 140px',
          gap: '14px',
          padding: '14px 16px',
          alignItems: 'center',
        }}
      >
        {/* Logo */}
        <div
          style={{
            width: '48px',
            height: '48px',
            borderRadius: '8px',
            background: gig.logoBg,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#ffffff',
            fontSize: '16px',
            fontWeight: '700',
          }}
        >
          {gig.logo}
        </div>

        {/* Title + client */}
        <div>
          <div style={{ fontSize: '13px', fontWeight: '600', color: ST.ink, marginBottom: '2px' }}>
            {gig.title}
          </div>
          <div style={{ fontSize: '11px', color: ST.ink3 }}>{gig.client}</div>
        </div>

        {/* Fit */}
        <div style={{ textAlign: 'center' }}>
          <div style={{ fontSize: '20px', fontWeight: '700', color: ST.brand, fontVariantNumeric: 'tabular-nums' }}>
            {gig.fit}%
          </div>
          <div style={{ fontSize: '9px', color: ST.ink4, marginTop: '2px' }}>Your fit</div>
        </div>

        {/* Rate */}
        <div style={{ textAlign: 'center' }}>
          <div style={{ fontSize: '13px', fontWeight: '600', color: ST.ink }}>{gig.rate}</div>
          <div style={{ fontSize: '9px', color: ST.ink3, marginTop: '2px' }}>{gig.commitment}</div>
        </div>

        {/* Duration */}
        <div style={{ textAlign: 'center' }}>
          <div style={{ fontSize: '13px', fontWeight: '600', color: ST.ink }}>{gig.duration}</div>
          <div style={{ fontSize: '9px', color: ST.ink3, marginTop: '2px' }}>Duration</div>
        </div>

        {/* Actions */}
        <div style={{ display: 'flex', gap: '6px', flexDirection: 'column' }}>
          <button
            style={{
              padding: '6px 10px',
              borderRadius: '6px',
              background: `linear-gradient(135deg, ${ST.brand} 0%, ${ST.brand2} 100%)`,
              fontSize: '11px',
              fontWeight: '600',
              color: '#ffffff',
              border: 'none',
              cursor: 'pointer',
            }}
          >
            Apply
          </button>
          <button
            style={{
              padding: '5px 10px',
              borderRadius: '6px',
              background: ST.panel2,
              border: `1px solid ${ST.border2}`,
              fontSize: '10px',
              color: ST.ink3,
              fontWeight: '500',
              cursor: 'pointer',
            }}
          >
            Save
          </button>
        </div>
      </div>

      {/* Info */}
      <div style={{ borderTop: `1px solid ${ST.divider}`, padding: '12px 16px', background: ST.panel2 }}>
        <div
          style={{
            fontSize: '8.5px',
            color: ST.ink4,
            textTransform: 'uppercase',
            fontWeight: '600',
            letterSpacing: '0.5px',
            marginBottom: '6px',
          }}
        >
          About This Gig
        </div>
        <p style={{ fontSize: '11px', color: ST.ink3, lineHeight: '1.4', margin: 0 }}>{gig.blurb}</p>

        {/* Focus tags */}
        <div style={{ display: 'flex', gap: '6px', marginTop: '8px', flexWrap: 'wrap' }}>
          {gig.focus.map((tag, i) => (
            <span
              key={i}
              style={{
                fontSize: '9px',
                padding: '2px 6px',
                background: ST.brandTint,
                color: ST.brand2,
                borderRadius: '3px',
                fontWeight: '500',
              }}
            >
              {tag}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}

// ============================================================================
// MAIN PAGE COMPONENT
// ============================================================================

export default function ScoutPage() {
  const [activeTab, setActiveTab] = useState<'vacancies' | 'future' | 'signals' | 'freelance'>('vacancies');
  const [vacancyFilters, setVacancyFilters] = useState<string[]>(['all']);
  const [signalTriggers, setSignalTriggers] = useState<string[]>([]);

  const filteredVacancies =
    vacancyFilters.includes('all') || vacancyFilters.length === 0
      ? VACANCIES
      : VACANCIES.filter((v) => {
          if (vacancyFilters.includes('90+') && v.match >= 90) return true;
          if (vacancyFilters.includes('75+') && v.match >= 75) return true;
          if (vacancyFilters.includes('Remote') && v.mode.includes('Remote')) return true;
          if (vacancyFilters.includes('NYC') && v.mode.includes('NYC')) return true;
          if (vacancyFilters.includes('SF') && v.mode.includes('SF')) return true;
          return false;
        });

  const filteredSignals =
    signalTriggers.length === 0 ? SIGNALS : SIGNALS.filter((s) => signalTriggers.includes(s.trig));

  return (
    <div style={{ fontFamily: 'Inter, system-ui, sans-serif', background: ST.bg, minHeight: '100vh' }}>
      <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.6; }
        }
        .pulse-dot {
          animation: pulse 2s infinite;
        }
      `}</style>

      {/* HEADER */}
      <div
        style={{
          padding: '28px 36px 18px',
          background: `linear-gradient(180deg, #fff 0%, ${ST.bg} 100%)`,
          borderBottom: `1px solid ${ST.border}`,
        }}
      >
        {/* Top row: Label + CTA */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '20px' }}>
          {/* Left: Label */}
          <div>
            <div
              style={{
                fontSize: '10px',
                letterSpacing: '1.6px',
                textTransform: 'uppercase',
                color: ST.ink4,
                fontFamily: "'JetBrains Mono', monospace",
                fontWeight: '600',
                marginBottom: '8px',
              }}
            >
              Job Scout · the hidden market
            </div>
            <h1
              style={{
                fontSize: '30px',
                fontWeight: '700',
                letterSpacing: '-1px',
                color: ST.ink,
                margin: '0 0 8px 0',
              }}
            >
              The Scout
            </h1>
            <p
              style={{
                fontSize: '13px',
                color: ST.ink3,
                margin: 0,
              }}
            >
              Discover opportunities before they're public. AI-powered signals, predictions, and market intelligence.
            </p>
          </div>

          {/* Right: CTA + Meta */}
          <div style={{ textAlign: 'right' }}>
            <button
              style={{
                padding: '16px 26px',
                borderRadius: '14px',
                background: `linear-gradient(135deg, ${ST.brand} 0%, ${ST.brand2} 100%)`,
                fontSize: '18px',
                fontWeight: '600',
                color: '#ffffff',
                border: 'none',
                cursor: 'pointer',
                marginBottom: '12px',
                boxShadow: '0 8px 22px rgba(91,108,255,0.30)',
              }}
            >
              Unleash the Scout
            </button>
            <div style={{ fontSize: '12px', color: ST.ink3, marginTop: '8px' }}>
              <span className="pulse-dot" style={{ display: 'inline-block', width: '7px', height: '7px', background: ST.brand, borderRadius: '50%', marginRight: '6px' }} />
              last scan 6m ago
            </div>
            <Link href="#" style={{ fontSize: '11px', color: ST.brand, textDecoration: 'none', fontWeight: '500', marginTop: '4px', display: 'inline-block' }}>
              edit watchlist
            </Link>
          </div>
        </div>

        {/* KPI Row */}
        <div
          style={{
            display: 'flex',
            gap: '24px',
            borderTop: `1px solid ${ST.divider}`,
            marginTop: '18px',
            paddingTop: '14px',
          }}
        >
          {[
            { label: 'Open Vacancies', value: '9' },
            { label: 'New Today', value: '2', delta: '+2' },
            { label: 'Avg Match', value: '76%' },
            { label: 'Watching', value: '14' },
          ].map((kpi, i) => (
            <div key={i}>
              <div
                style={{
                  fontSize: '9.5px',
                  color: ST.ink4,
                  textTransform: 'uppercase',
                  letterSpacing: '1px',
                  fontWeight: '600',
                  marginBottom: '2px',
                }}
              >
                {kpi.label}
              </div>
              <div
                style={{
                  fontSize: '20px',
                  fontWeight: '700',
                  color: ST.ink,
                  letterSpacing: '-0.4px',
                  fontVariantNumeric: 'tabular-nums',
                }}
              >
                {kpi.value}
              </div>
              {kpi.delta && (
                <div style={{ fontSize: '10px', fontWeight: '600', color: '#16a34a', marginTop: '2px' }}>
                  {kpi.delta}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* BRIEFING */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'auto 1fr auto',
          gap: '18px',
          padding: '12px 36px',
          background: `linear-gradient(90deg, rgba(91,108,255,0.06), rgba(91,108,255,0.02) 50%, transparent)`,
          borderBottom: '1px solid rgba(91,108,255,0.18)',
          alignItems: 'center',
        }}
      >
        <div style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
          <div className="pulse-dot" style={{ width: '7px', height: '7px', background: ST.brand, borderRadius: '50%' }} />
          <span style={{ fontSize: '10px', fontFamily: "'JetBrains Mono', monospace", color: ST.brand2 }}>Since you last looked</span>
        </div>
        <div style={{ fontSize: '12.5px', color: ST.ink2 }}>
          3 new vacancies · <strong>Linear</strong> Head of Product went live (was tracked 4d) · 1 stale lead aging out
        </div>
        <button
          style={{
            padding: '6px 12px',
            borderRadius: '6px',
            background: `linear-gradient(135deg, ${ST.brand} 0%, ${ST.brand2} 100%)`,
            fontSize: '11.5px',
            fontWeight: '600',
            color: '#ffffff',
            border: 'none',
            cursor: 'pointer',
            whiteSpace: 'nowrap',
          }}
        >
          Review new matches
        </button>
      </div>

      {/* TAB BAR */}
      <div
        style={{
          padding: '0 36px',
          borderBottom: `1px solid ${ST.border}`,
          background: ST.panel,
          display: 'flex',
        }}
      >
        {[
          { id: 'vacancies', label: 'Vacancies', count: 9 },
          { id: 'future', label: 'Future (Predicted Roles)', count: 5 },
          { id: 'signals', label: 'Signals', count: 18 },
          { id: 'freelance', label: 'Freelance', count: 14 },
        ].map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id as any)}
            style={{
              padding: '14px 18px',
              fontSize: '13px',
              fontWeight: activeTab === tab.id ? '600' : '500',
              color: activeTab === tab.id ? ST.brand : ST.ink3,
              borderBottom: activeTab === tab.id ? `2px solid ${ST.brand}` : '2px solid transparent',
              background: 'transparent',
              border: 'none',
              cursor: 'pointer',
            }}
          >
            {tab.label} ({tab.count})
          </button>
        ))}
      </div>

      {/* CONTENT */}
      <div style={{ padding: '36px' }}>
        {activeTab === 'vacancies' && (
          <>
            {/* Headline */}
            <div style={{ marginBottom: '24px' }}>
              <h2
                style={{
                  fontSize: '22px',
                  fontWeight: '600',
                  color: ST.ink,
                  margin: '0 0 6px 0',
                }}
              >
                9 open roles match your profile.{' '}
                <span style={{ color: ST.brand }}>2 posted in the last 6 hours.</span>
              </h2>
              <p style={{ fontSize: '13px', color: ST.ink3, margin: 0, marginTop: '6px' }}>
                These vacancies are live on the public job market right now. Match scores reflect your skill graph against each role's requirements.
              </p>
            </div>

            {/* Filter bar */}
            <div
              style={{
                display: 'flex',
                gap: '10px',
                padding: '14px 36px',
                marginLeft: '-36px',
                marginRight: '-36px',
                background: ST.panel2,
                borderBottom: `1px solid ${ST.divider}`,
                marginBottom: '24px',
              }}
            >
              {[
                { id: 'all', label: 'All (9)' },
                { id: '90+', label: '90+ (1)' },
                { id: '75+', label: '75+ (3)' },
                { id: 'Remote', label: 'Remote (5)' },
                { id: 'NYC', label: 'NYC (2)' },
                { id: 'SF', label: 'SF (3)' },
              ].map((filter) => (
                <button
                  key={filter.id}
                  onClick={() =>
                    setVacancyFilters(
                      vacancyFilters.includes(filter.id)
                        ? vacancyFilters.filter((f) => f !== filter.id)
                        : [filter.id]
                    )
                  }
                  style={{
                    padding: '8px 14px',
                    borderRadius: '6px',
                    fontSize: '12px',
                    fontWeight: vacancyFilters.includes(filter.id) ? '600' : '500',
                    color: vacancyFilters.includes(filter.id) ? ST.brand : ST.ink3,
                    background: vacancyFilters.includes(filter.id) ? ST.brandTint2 : ST.panel,
                    border: `1px solid ${vacancyFilters.includes(filter.id) ? ST.brand : ST.border}`,
                    cursor: 'pointer',
                  }}
                >
                  {filter.label}
                </button>
              ))}
            </div>

            {/* Cards */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              {filteredVacancies.map((vacancy) => (
                <VacancyCard key={vacancy.id} vacancy={vacancy} />
              ))}
            </div>
          </>
        )}

        {activeTab === 'future' && (
          <>
            {/* Headline */}
            <div style={{ marginBottom: '24px' }}>
              <h2
                style={{
                  fontSize: '22px',
                  fontWeight: '600',
                  color: ST.ink,
                  margin: '0 0 6px 0',
                }}
              >
                5 roles we think are forming.{' '}
                <span style={{ color: ST.brand }}>2 have a confidence above 80%.</span>
              </h2>
              <p style={{ fontSize: '13px', color: ST.ink3, margin: 0, marginTop: '6px' }}>
                These jobs don't exist yet, but our models predict they will within the next 90 days based on company signals, hiring patterns, and org chart gaps.
              </p>
            </div>

            {/* KPIs */}
            <div
              style={{
                display: 'flex',
                gap: '24px',
                marginBottom: '24px',
                paddingBottom: '14px',
                borderBottom: `1px solid ${ST.divider}`,
              }}
            >
              {[
                { label: 'Predicted Roles', value: '5' },
                { label: 'Avg Confidence', value: '70%' },
                { label: 'New This Week', value: '2' },
                { label: 'Converted to Vacancy', value: '3' },
              ].map((kpi, i) => (
                <div key={i}>
                  <div
                    style={{
                      fontSize: '9.5px',
                      color: ST.ink4,
                      textTransform: 'uppercase',
                      letterSpacing: '1px',
                      fontWeight: '600',
                      marginBottom: '2px',
                    }}
                  >
                    {kpi.label}
                  </div>
                  <div style={{ fontSize: '18px', fontWeight: '700', color: ST.ink }}>
                    {kpi.value}
                  </div>
                </div>
              ))}
            </div>

            {/* Cards */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
              {PREDICTIONS.map((pred, i) => (
                <PredictionCard key={i} pred={pred} />
              ))}
            </div>
          </>
        )}

        {activeTab === 'signals' && (
          <>
            {/* Headline */}
            <div style={{ marginBottom: '24px' }}>
              <h2
                style={{
                  fontSize: '22px',
                  fontWeight: '600',
                  color: ST.ink,
                  margin: '0 0 6px 0',
                }}
              >
                18 hiring signals detected this week.{' '}
                <span style={{ color: ST.brand }}>3 are high-impact for your profile.</span>
              </h2>
              <p style={{ fontSize: '13px', color: ST.ink3, margin: 0, marginTop: '6px' }}>
                Live feed of funding rounds, leadership moves, and expansion signals across your tracked companies and industries.
              </p>
            </div>

            {/* KPIs */}
            <div
              style={{
                display: 'flex',
                gap: '24px',
                marginBottom: '24px',
                paddingBottom: '14px',
                borderBottom: `1px solid ${ST.divider}`,
              }}
            >
              {[
                { label: 'Signals This Week', value: '18' },
                { label: 'High Impact', value: '3' },
                { label: 'New Today', value: '4' },
                { label: 'Companies Tracked', value: '142' },
              ].map((kpi, i) => (
                <div key={i}>
                  <div
                    style={{
                      fontSize: '9.5px',
                      color: ST.ink4,
                      textTransform: 'uppercase',
                      letterSpacing: '1px',
                      fontWeight: '600',
                      marginBottom: '2px',
                    }}
                  >
                    {kpi.label}
                  </div>
                  <div style={{ fontSize: '18px', fontWeight: '700', color: ST.ink }}>
                    {kpi.value}
                  </div>
                </div>
              ))}
            </div>

            {/* Trigger filter */}
            <div
              style={{
                display: 'flex',
                gap: '12px',
                marginBottom: '24px',
                padding: '12px 0',
              }}
            >
              {Object.entries(TRIG).map(([trigKey, trigColor]) => (
                <button
                  key={trigKey}
                  onClick={() =>
                    setSignalTriggers(
                      signalTriggers.includes(trigKey)
                        ? signalTriggers.filter((t) => t !== trigKey)
                        : [...signalTriggers, trigKey]
                    )
                  }
                  style={{
                    width: '12px',
                    height: '12px',
                    borderRadius: '50%',
                    background: trigColor,
                    border: signalTriggers.includes(trigKey) ? `2px solid ${ST.ink}` : 'none',
                    cursor: 'pointer',
                    padding: signalTriggers.includes(trigKey) ? '0' : '2px',
                  }}
                  title={trigKey}
                />
              ))}
            </div>

            {/* Lead story */}
            <div style={{ marginBottom: '28px' }}>
              <SignalCard signal={SIGNALS[0]} isLead={true} />
            </div>

            {/* Clippings grid */}
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(2, 1fr)',
                gap: '12px',
              }}
            >
              {filteredSignals.slice(1).map((signal) => (
                <SignalCard key={signal.id} signal={signal} />
              ))}
            </div>
          </>
        )}

        {activeTab === 'freelance' && (
          <>
            {/* Headline */}
            <div style={{ marginBottom: '24px' }}>
              <h2
                style={{
                  fontSize: '22px',
                  fontWeight: '600',
                  color: ST.ink,
                  margin: '0 0 6px 0',
                }}
              >
                14 advisory and fractional gigs match your profile.
              </h2>
              <p style={{ fontSize: '13px', color: ST.ink3, margin: 0, marginTop: '6px' }}>
                Curated from A.Team, Toptal, Catalant, and Braintrust. We match your expertise against market rates and client caliber.
              </p>
            </div>

            {/* KPIs */}
            <div
              style={{
                display: 'flex',
                gap: '24px',
                marginBottom: '24px',
                paddingBottom: '14px',
                borderBottom: `1px solid ${ST.divider}`,
              }}
            >
              {[
                { label: 'Gigs Available', value: '14' },
                { label: 'Avg Day Rate', value: '$1,180' },
                { label: 'New This Week', value: '5' },
                { label: 'Your Fit Avg', value: '78%' },
              ].map((kpi, i) => (
                <div key={i}>
                  <div
                    style={{
                      fontSize: '9.5px',
                      color: ST.ink4,
                      textTransform: 'uppercase',
                      letterSpacing: '1px',
                      fontWeight: '600',
                      marginBottom: '2px',
                    }}
                  >
                    {kpi.label}
                  </div>
                  <div style={{ fontSize: '18px', fontWeight: '700', color: ST.ink }}>
                    {kpi.value}
                  </div>
                </div>
              ))}
            </div>

            {/* Marketplace filter */}
            <div
              style={{
                display: 'flex',
                gap: '16px',
                marginBottom: '24px',
                paddingBottom: '12px',
              }}
            >
              {MARKETS.map((market) => (
                <div key={market.id} style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <span
                    style={{
                      width: '10px',
                      height: '10px',
                      borderRadius: '50%',
                      background: market.color,
                    }}
                  />
                  <span style={{ fontSize: '12px', color: ST.ink3 }}>
                    {market.label} ({market.count})
                  </span>
                </div>
              ))}
            </div>

            {/* Gig cards */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              {GIGS.map((gig) => (
                <GigCard key={gig.id} gig={gig} />
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
