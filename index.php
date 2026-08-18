<?php
/**
 * PlaceboPay - a fake payment gateway placeholder for demos and prototypes.
 *
 * Single file. No database. No dependencies. No real payments.
 *
 * Drop this file on any PHP host (e.g. /pay/index.php) and point your
 * checkout button at it:
 *
 *   /pay/?name=Demo+Shop&amount=49.90&currency=EUR
 *        &success_url=https://your-app.test/checkout/return
 *
 * The visitor sees a realistic hosted-checkout page with three explicit
 * buttons: approve, decline, cancel. Clicking one returns them to your
 * URL with ?placebopay=1&status=success|failed|cancelled&txn_id=...
 *
 * Anti-abuse design (please keep these intact if you fork):
 *   - The page contains ZERO input fields. Nothing can be typed or
 *     harvested here, which makes it useless for phishing.
 *   - It never redirects automatically. Every redirect is an explicit,
 *     clearly labelled click, and the destination domain is shown.
 *   - A permanent TEST MODE banner states that no real payment occurs.
 *   - The page is noindex and refuses to be iframed.
 *
 * https://placebopay.dev | MIT License
 */

/* ---------------------------------------------------------------------
 * CONFIG - the only part you may want to edit
 * ------------------------------------------------------------------- */

// Restrict which hosts you are willing to redirect back to.
// Empty array = allow any host (fine for local/self-hosted use).
// Example: ['myapp.test', 'staging.example.com']
const ALLOWED_RETURN_HOSTS = [];

// Maximum simulated processing delay in seconds (?delay=N is clamped to this).
const MAX_DELAY_SECONDS = 10;

// Shown in the footer so people can report misuse of your instance.
const REPORT_URL = 'https://github.com/elaz48/placebopay/issues';

// Public docs link shown when the page is opened without parameters.
const DOCS_URL = 'https://placebopay.dev';

/* ---------------------------------------------------------------------
 * No user-serviceable parts below (unless you enjoy that sort of thing)
 * ------------------------------------------------------------------- */

header('X-Frame-Options: DENY');
header('X-Content-Type-Options: nosniff');
header('Referrer-Policy: no-referrer');
header('X-Robots-Tag: noindex, nofollow');
header("Content-Security-Policy: default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; img-src data:");

function e(string $s): string {
    return htmlspecialchars($s, ENT_QUOTES, 'UTF-8');
}

/** Validate a return URL. Returns the normalized URL or null if unsafe. */
function valid_return_url(?string $url): ?string {
    if ($url === null || $url === '' || strlen($url) > 2000) return null;
    $p = parse_url($url);
    if ($p === false) return null;
    if (!isset($p['scheme'], $p['host'])) return null;
    $scheme = strtolower($p['scheme']);
    if ($scheme !== 'http' && $scheme !== 'https') return null;
    // Refuse credentials embedded in the URL (classic phishing trick).
    if (isset($p['user']) || isset($p['pass'])) return null;
    if (ALLOWED_RETURN_HOSTS !== []) {
        $host = strtolower($p['host']);
        $ok = false;
        foreach (ALLOWED_RETURN_HOSTS as $allowed) {
            if ($host === strtolower($allowed)) { $ok = true; break; }
        }
        if (!$ok) return null;
    }
    return $url;
}

/** Append query parameters to a URL, preserving existing query and fragment. */
function with_params(string $url, array $params): string {
    $p = parse_url($url);
    $query = [];
    if (isset($p['query'])) parse_str($p['query'], $query);
    $query = array_merge($query, $params);

    $out  = $p['scheme'] . '://' . $p['host'];
    if (isset($p['port']))  $out .= ':' . $p['port'];
    $out .= $p['path'] ?? '/';
    $out .= '?' . http_build_query($query);
    if (isset($p['fragment'])) $out .= '#' . $p['fragment'];
    return $out;
}

/** Read and sanitize a short, display-safe text parameter. */
function text_param(string $key, int $maxLen, string $default = ''): string {
    $v = $_GET[$key] ?? $default;
    if (!is_string($v)) return $default;
    $v = trim(preg_replace('/[\x00-\x1F\x7F]/u', '', $v) ?? '');
    if (function_exists('mb_substr')) {
        $v = mb_substr($v, 0, $maxLen, 'UTF-8');
    } else {
        $v = substr($v, 0, $maxLen);
    }
    return $v;
}

/* ----- Read parameters ------------------------------------------------ */

$successUrl = valid_return_url(is_string($_GET['success_url'] ?? null) ? $_GET['success_url'] : null);
$cancelUrl  = valid_return_url(is_string($_GET['cancel_url']  ?? null) ? $_GET['cancel_url']  : null) ?? $successUrl;
$failUrl    = valid_return_url(is_string($_GET['fail_url']    ?? null) ? $_GET['fail_url']    : null) ?? $successUrl;

$shopName = text_param('name', 60, 'Example Merchant');

$amountRaw = $_GET['amount'] ?? '';
$amount = (is_string($amountRaw) && preg_match('/^\d{1,9}([.,]\d{1,2})?$/', $amountRaw))
    ? str_replace(',', '.', $amountRaw)
    : null;

$currencyRaw = $_GET['currency'] ?? '';
$currency = (is_string($currencyRaw) && preg_match('/^[A-Za-z]{3}$/', $currencyRaw))
    ? strtoupper($currencyRaw)
    : null;

$ref = text_param('ref', 40);
$ref = preg_replace('/[^A-Za-z0-9._-]/', '', $ref) ?? '';

$delay = min(MAX_DELAY_SECONDS, max(0, (int)($_GET['delay'] ?? 0)));

$txnId = 'PLB_' . bin2hex(random_bytes(8));

/* ----- Build outcome links -------------------------------------------- */

$links = null;
$returnHost = null;
if ($successUrl !== null) {
    $base = ['placebopay' => '1', 'txn_id' => $txnId];
    if ($ref !== '') $base['ref'] = $ref;
    $links = [
        'success'   => with_params($successUrl, $base + ['status' => 'success']),
        'failed'    => with_params($failUrl,    $base + ['status' => 'failed']),
        'cancelled' => with_params($cancelUrl,  $base + ['status' => 'cancelled']),
    ];
    $returnHost = parse_url($successUrl, PHP_URL_HOST);
}

$displayAmount = null;
if ($amount !== null) {
    $displayAmount = number_format((float)$amount, 2, '.', ' ');
    if ($currency !== null) $displayAmount .= ' ' . $currency;
}
?>
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow">
<title>PlaceboPay checkout (test mode)</title>
<style>
  :root {
    --paper:#f4f7f5; --card:#ffffff; --ink:#17251f; --muted:#5d6f66;
    --line:#dde5e0; --green:#0e8f62; --green-dark:#0b7450;
    --red:#b3402f; --amber:#8a6d1f; --amber-bg:#fdf3d7; --amber-line:#eeda9d;
  }
  * { box-sizing:border-box; margin:0; padding:0; }
  body {
    font:16px/1.55 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    background:var(--paper); color:var(--ink);
    min-height:100vh; display:flex; flex-direction:column; align-items:center;
  }
  .banner {
    width:100%; background:var(--amber-bg); border-bottom:1px solid var(--amber-line);
    color:var(--amber); text-align:center; padding:10px 16px;
    font-size:13.5px; font-weight:600; letter-spacing:.02em;
  }
  .banner strong { text-transform:uppercase; letter-spacing:.08em; }
  main { width:100%; max-width:430px; padding:36px 20px 24px; flex:1; }
  .card {
    background:var(--card); border:1px solid var(--line); border-radius:14px;
    box-shadow:0 8px 28px rgba(23,37,31,.07); overflow:hidden;
  }
  .card-head { padding:22px 24px 18px; border-bottom:1px solid var(--line); }
  .merchant { font-size:13px; color:var(--muted); }
  .shop { font-size:19px; font-weight:700; margin-top:2px; overflow-wrap:anywhere; }
  .amount { font-size:32px; font-weight:800; letter-spacing:-.01em; margin-top:12px; }
  .ref { font-size:12.5px; color:var(--muted); margin-top:4px; font-family:ui-monospace,Menlo,Consolas,monospace; }
  .card-body { padding:20px 24px 24px; }
  .fakecard {
    border:1px dashed var(--line); border-radius:10px; padding:14px 16px;
    background:#fafcfb; margin-bottom:20px;
  }
  .fakecard .label { font-size:11px; text-transform:uppercase; letter-spacing:.08em; color:var(--muted); }
  .fakecard .num { font-family:ui-monospace,Menlo,Consolas,monospace; font-size:16px; margin-top:4px; letter-spacing:.06em; }
  .fakecard .note { font-size:12px; color:var(--muted); margin-top:6px; }
  .btn {
    display:block; width:100%; text-align:center; text-decoration:none;
    padding:13px 16px; border-radius:10px; font-weight:700; font-size:15.5px;
    margin-top:10px; border:1px solid transparent; cursor:pointer;
  }
  .btn:focus-visible { outline:3px solid #9fd9c2; outline-offset:2px; }
  .btn-success { background:var(--green); color:#fff; }
  .btn-success:hover { background:var(--green-dark); }
  .btn-fail { background:#fff; color:var(--red); border-color:#e3c4bd; }
  .btn-fail:hover { background:#fbf1ef; }
  .btn-cancel { background:none; color:var(--muted); font-weight:600; font-size:14px; }
  .btn-cancel:hover { color:var(--ink); }
  .return-note {
    margin-top:16px; font-size:13px; color:var(--muted); text-align:center;
  }
  .return-note code {
    font-family:ui-monospace,Menlo,Consolas,monospace; color:var(--ink);
    background:#eef3f0; padding:1px 6px; border-radius:5px; overflow-wrap:anywhere;
  }
  footer {
    padding:18px 20px 26px; font-size:12.5px; color:var(--muted); text-align:center; max-width:520px;
  }
  footer a { color:var(--muted); }
  .overlay {
    position:fixed; inset:0; background:rgba(244,247,245,.94); display:none;
    align-items:center; justify-content:center; flex-direction:column; gap:14px;
    font-weight:600; color:var(--ink);
  }
  .spinner {
    width:34px; height:34px; border-radius:50%;
    border:4px solid var(--line); border-top-color:var(--green);
    animation:spin .8s linear infinite;
  }
  @keyframes spin { to { transform:rotate(360deg); } }
  @media (prefers-reduced-motion:reduce) { .spinner { animation:none; } }
  .docs { padding:26px 24px; }
  .docs h1 { font-size:20px; margin-bottom:10px; }
  .docs p { color:var(--muted); font-size:14.5px; margin-bottom:12px; }
  .docs pre {
    background:#eef3f0; border-radius:8px; padding:12px 14px; font-size:12.5px;
    font-family:ui-monospace,Menlo,Consolas,monospace; overflow-x:auto; white-space:pre;
  }
  .docs a.btn { max-width:260px; margin:16px auto 0; }
</style>
</head>
<body>

<div class="banner">
  <strong>Test mode</strong> &middot; This is a simulated payment page. No real payment will be processed and no card data is collected.
</div>

<main>
<?php if ($links === null): ?>
  <div class="card docs">
    <h1>PlaceboPay</h1>
    <p>A fake payment gateway placeholder. Point your checkout button here with a
       <code>success_url</code> parameter and you will get a realistic hosted-checkout
       page that only ever does one thing: send the visitor back to you with a chosen outcome.</p>
    <pre><?php echo e((isset($_SERVER['HTTPS']) ? 'https' : 'http') . '://' . ($_SERVER['HTTP_HOST'] ?? 'placebopay.dev') . strtok($_SERVER['REQUEST_URI'] ?? '/', '?')); ?>
  ?name=Demo+Shop
  &amp;amount=49.90
  &amp;currency=EUR
  &amp;ref=ORDER-1042
  &amp;delay=2
  &amp;success_url=https://your-app.test/return</pre>
    <p>Returns to your URL with <code>?placebopay=1&amp;status=success|failed|cancelled&amp;txn_id=PLB_...&amp;ref=...</code></p>
    <a class="btn btn-success" href="<?php echo e(DOCS_URL); ?>">Read the docs</a>
  </div>
<?php else: ?>
  <div class="card">
    <div class="card-head">
      <div class="merchant">Payment to</div>
      <div class="shop"><?php echo e($shopName); ?></div>
      <?php if ($displayAmount !== null): ?>
        <div class="amount"><?php echo e($displayAmount); ?></div>
      <?php endif; ?>
      <?php if ($ref !== ''): ?>
        <div class="ref">Reference: <?php echo e($ref); ?></div>
      <?php endif; ?>
    </div>
    <div class="card-body">
      <div class="fakecard">
        <div class="label">Payment method (simulated)</div>
        <div class="num">4242 4242 4242 4242 &nbsp; 12/34 &nbsp; 000</div>
        <div class="note">Nothing to fill in. This page has no input fields by design.</div>
      </div>

      <a class="btn btn-success" href="<?php echo e($links['success']); ?>" data-delay="<?php echo (int)$delay; ?>">Approve payment</a>
      <a class="btn btn-fail" href="<?php echo e($links['failed']); ?>" data-delay="<?php echo (int)$delay; ?>">Decline payment</a>
      <a class="btn btn-cancel" href="<?php echo e($links['cancelled']); ?>">Cancel and return</a>

      <div class="return-note">
        You will be returned to <code><?php echo e((string)$returnHost); ?></code><br>
        Transaction ID: <code><?php echo e($txnId); ?></code>
      </div>
    </div>
  </div>
<?php endif; ?>
</main>

<footer>
  PlaceboPay is a free developer tool for demos and prototypes. It never processes real payments.<br>
  If you believe this page is being misused,
  <a href="<?php echo e(REPORT_URL); ?>" rel="noopener">report it on GitHub</a>.
</footer>

<div class="overlay" id="overlay" role="status">
  <div class="spinner" aria-hidden="true"></div>
  <div>Processing simulated payment&hellip;</div>
</div>

<script>
// Optional simulated processing delay. Purely cosmetic and only runs after
// an explicit click. With JavaScript disabled the links work instantly.
(function () {
  var overlay = document.getElementById('overlay');
  var buttons = document.querySelectorAll('a[data-delay]');
  for (var i = 0; i < buttons.length; i++) {
    buttons[i].addEventListener('click', function (ev) {
      var d = parseInt(this.getAttribute('data-delay'), 10) || 0;
      if (d <= 0) return; // no delay, follow the link normally
      ev.preventDefault();
      var href = this.getAttribute('href');
      overlay.style.display = 'flex';
      setTimeout(function () { window.location.href = href; }, d * 1000);
    });
  }
})();
</script>

</body>
</html>
