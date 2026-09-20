import { experimental_evaluate as evaluate } from 'ai';

if (!process.env.AI_GATEWAY_API_KEY) {
  console.error('AI_GATEWAY_API_KEY が設定されていません。');
  console.error('例: AI_GATEWAY_API_KEY=... npm start');
  process.exit(1);
}

const state = `
お客様から次の問い合わせが届きました。

「昨日からクレジットカード決済が何度試しても失敗します。
明日のイベントで必要なので、至急直してもらえませんか？」
`.trim();

const result = await evaluate({
  model: 'typesafe-ai/jev',
  state,
  questions: {
    department: {
      type: 'choice',
      instructions: 'この問い合わせを担当すべき部署を選んでください。',
      criteria: {
        'billing': '請求、支払い、返金に関する問題',
        'technical-support': '製品や決済機能の技術的な不具合',
        'sales': '購入前の相談、価格、契約に関する質問',
      },
    },
    urgency: {
      type: 'score',
      instructions: '問い合わせの緊急度を評価してください。',
      criteria: [
        '急いでおらず、通常の対応でよい',
        '多少急いでいるが、即時対応は不要',
        '期限が迫っており、至急対応が必要',
      ],
    },
    paymentRelated: {
      type: 'boolean',
      instructions: 'この問い合わせは支払いに関係していますか？',
    },
  },
});

console.dir(result, { depth: null, colors: true });
