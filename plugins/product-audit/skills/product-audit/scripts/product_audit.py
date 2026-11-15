#!/usr/bin/env python3
"""Deterministic helpers for the product-audit skill.

Subcommands:

  scan  --root DIR [--out FILE] [--window-days N]
        Produce a JSON inventory of the product's surface: what it says it is, the
        screens, endpoints, commands, data models, settings, and integrations the code
        carries, when each arrived, and where recent work went. Read-only, no network.

  check --report FILE
        Validate the structure of a product audit report. Exit 1 with one error per
        line when the report is malformed or breaks an audit rule.

Every path the scan reports is relative to the root. Environment files are never
opened, so no secret value can appear in the output.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path
from typing import NoReturn

try:  # Python 3.11+
    import tomllib
except ImportError:  # pragma: no cover - older interpreters fall back to regexes
    tomllib = None

SCAN_SCHEMA = "product-audit-scan/v1"
REPORT_MARKER = "<!-- product-audit: v1 -->"
SCAN_NAME = ".product-audit-scan.json"

SKIP_DIRS = {
    ".git", "node_modules", ".venv", "venv", "env", "__pycache__", "dist", "build", "out",
    ".next", ".nuxt", ".output", ".svelte-kit", ".expo", ".turbo", ".vercel", ".angular",
    "target", "vendor", ".cache", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".tox",
    "coverage", ".idea", ".vscode", ".terraform", "Pods", ".gradle", ".dart_tool",
    "DerivedData", "storybook-static", ".parcel-cache", "bower_components", ".yarn",
    "site-packages",
}
# Directories whose contents are not the product a user meets.
NON_PRODUCT_DIRS = {
    "test", "tests", "__tests__", "spec", "specs", "e2e", "cypress", "playwright",
    "__mocks__", "mocks", "fixtures", "__fixtures__", "examples", "example", "samples",
    "demo", "demos", "docs", "doc", "stories", ".storybook", "storybook", "benchmarks",
    "bench", "scripts", "tools", "qa", ".github",
}
TEST_FILE_RE = re.compile(r"(\.test\.|\.spec\.|_test\.|^test_|\.stories\.|\.d\.ts$)")
MAX_FILES = 8000
MAX_CONTENT_BYTES = 512 * 1024
MAX_TOTAL_BYTES = 96 * 1024 * 1024
MAX_LIST = 200
TEXT_CLIP = 400

JS_SUFFIXES = {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"}
MARKUP_SUFFIXES = {".jsx", ".tsx", ".vue", ".svelte", ".astro", ".html", ".erb", ".ejs", ".hbs", ".njk"}
NATIVE_UI_SUFFIXES = {".dart", ".swift", ".kt"}
UI_SUFFIXES = MARKUP_SUFFIXES | NATIVE_UI_SUFFIXES
SOURCE_SUFFIXES = JS_SUFFIXES | {
    ".py", ".rb", ".go", ".rs", ".java", ".kt", ".swift", ".php", ".cs", ".dart", ".vue",
    ".svelte", ".astro", ".ex", ".exs",
}
TEXT_SUFFIXES = SOURCE_SUFFIXES | MARKUP_SUFFIXES | {
    ".md", ".mdx", ".txt", ".rst", ".json", ".yaml", ".yml", ".toml", ".sql", ".prisma",
    ".graphql", ".gql", ".gradle", ".kts", ".webmanifest", ".mod",
}
BARE_TEXT_NAMES = {"Gemfile", "Podfile", "Pipfile"}
README_RE = re.compile(r"^readme(\.(md|markdown|rst|txt))?$", re.IGNORECASE)
HTML_TAG_RE = re.compile(r"<[^>]+>")
DIRECTION_DOC_RE = re.compile(
    r"(^|[-_. ])(roadmap|todo|todos|plan|plans|planning|ideas|backlog|vision|prd|strategy|"
    r"milestones|shortlist)([-_. ]|$)",
    re.IGNORECASE,
)
RELEASE_NOTES_RE = re.compile(r"^(changelog|changes|history|releases|release[-_ ]notes)(\.(md|markdown|txt|rst))?$", re.IGNORECASE)
FEATURE_HEADING_RE = re.compile(
    r"^(#{1,4})\s+.*\b(features?|highlights|capabilities|functionality|what (it|you) (does|can do)|"
    r"what's included|what is included)\b",
    re.IGNORECASE,
)
HEADING_RE = re.compile(r"^(#{1,6})\s+\S")
BULLET_RE = re.compile(r"^\s{0,3}(?:[-*+]|\d+[.)])\s+(.+?)\s*$")

# --------------------------------------------------------------------------- stack and services

STACK_MARKERS = {
    "next": "next", "react": "react", "react-dom": "react", "react-native": "react-native",
    "expo": "expo", "expo-router": "expo-router", "vue": "vue", "nuxt": "nuxt",
    "svelte": "svelte", "@sveltejs/kit": "sveltekit", "@remix-run/react": "remix",
    "@react-router/dev": "remix", "@tanstack/react-router": "tanstack-router",
    "react-router": "react-router", "react-router-dom": "react-router",
    "vue-router": "vue-router", "astro": "astro", "solid-js": "solid",
    "@angular/core": "angular", "electron": "electron", "@tauri-apps/api": "tauri",
    "express": "express", "fastify": "fastify", "hono": "hono", "koa": "koa",
    "@nestjs/core": "nestjs", "@trpc/server": "trpc", "commander": "commander",
    "yargs": "yargs", "cac": "cac", "@react-navigation/native": "react-navigation",
    "django": "django", "flask": "flask", "fastapi": "fastapi", "click": "click",
    "typer": "typer", "rails": "rails", "sinatra": "sinatra", "flutter": "flutter",
    "github.com/spf13/cobra": "cobra", "github.com/gin-gonic/gin": "gin",
    "github.com/labstack/echo": "echo", "github.com/go-chi/chi": "chi", "clap": "clap",
    "axum": "axum", "actix-web": "actix", "laravel/framework": "laravel",
    "phoenix": "phoenix", "prisma": "prisma", "@prisma/client": "prisma",
    "drizzle-orm": "drizzle", "convex": "convex",
}

# (pattern searched in a normalized dependency name, service, kind)
INTEGRATIONS = [
    (r"^stripe$|^@stripe/|^stripe-|com\.stripe", "Stripe", "payments"),
    (r"^@paddle/|^paddle-|^@lemonsqueezy/|^lemonsqueezy", "Paddle or Lemon Squeezy", "payments"),
    (r"paypal|braintree", "PayPal", "payments"),
    (r"^react-native-purchases$|^purchases-|revenuecat", "RevenueCat", "payments"),
    (r"^openai$|^@ai-sdk/openai$", "OpenAI", "ai"),
    (r"^@anthropic-ai/|^anthropic$|^@ai-sdk/anthropic$", "Anthropic", "ai"),
    (r"^@google/generative-ai$|^@google/genai$|^google-generativeai$|^google-genai$|^@ai-sdk/google", "Google AI", "ai"),
    (r"^langchain|^@langchain/|^llama-index|^llamaindex$", "LLM framework", "ai"),
    (r"^ai$", "Vercel AI SDK", "ai"),
    (r"^replicate$|^cohere|^@huggingface/|^huggingface-hub$|^ollama$|^@mistralai/|^mistralai$|^groq", "Model provider", "ai"),
    (r"^next-auth$|^@auth/|^@clerk/|^clerk-|^@auth0/|^auth0|^passport$|^lucia$|^better-auth$|^django-allauth$|^authlib$|^devise$|^@supabase/auth-|^@workos-inc/|^firebase-auth", "Auth provider", "auth"),
    (r"^resend$|^@sendgrid/|^sendgrid$|^nodemailer$|^postmark|^mailgun|^@mailchimp/|^mailchimp", "Email", "email"),
    (r"^twilio$|^@slack/|^slack-sdk$|^slack-bolt$|^discord\.js$|^discord\.py$|^discord$|^telegraf$|^python-telegram-bot$|^node-telegram-bot-api$|^grammy$", "Messaging", "messaging"),
    (r"^posthog|^mixpanel|^@amplitude/|^amplitude|^@segment/|^analytics-node$|^plausible|^@vercel/analytics$|^react-ga4?$|^@umami/|^@react-native-firebase/analytics$|^firebase-analytics|^@google-analytics/|^vue-gtag$|^@aptabase/", "Product analytics", "analytics"),
    (r"^@sentry/|^sentry-sdk$|^sentry-|^@bugsnag/|^bugsnag|^rollbar$|^logrocket$|^@datadog/|^ddtrace$|^newrelic$", "Monitoring", "monitoring"),
    (r"^firebase$|^firebase-admin$|^@react-native-firebase/app$|^firebase-core$|^cloud-firestore$", "Firebase", "backend"),
    (r"^@supabase/supabase-js$|^supabase$|^supabase-flutter$|^@supabase/ssr$", "Supabase", "backend"),
    (r"^@aws-sdk/|^aws-sdk$|^boto3$|^@google-cloud/|^@azure/|^appwrite$|^node-appwrite$|^pocketbase$", "Cloud SDK", "backend"),
    (r"^@planetscale/|^@neondatabase/|^@upstash/|^@vercel/(kv|postgres|blob)$|^@libsql/|^ioredis$|^redis$", "Hosted data", "data"),
    (r"^cloudinary$|^uploadthing$|^@uploadthing/|^@mux/|^imagekit", "Media", "media"),
    (r"^algoliasearch$|^meilisearch$|^typesense$|^@elastic/|^@pinecone-database/|^pinecone|^chromadb$|^weaviate", "Search or vectors", "search"),
    (r"^mapbox-gl$|^@googlemaps/|^@react-google-maps/|^react-native-maps$|^google-maps", "Maps", "maps"),
    (r"^pusher|^ably$|^livekit|^@liveblocks/|^partykit$", "Realtime", "realtime"),
    (r"^expo-notifications$|^onesignal|^react-native-onesignal$|^web-push$|^firebase-messaging$|^@react-native-firebase/messaging$|^@novu/|^@knocklabs/", "Notifications", "notifications"),
    (r"launchdarkly|^@growthbook/|^flagsmith|^unleash|^@vercel/flags$|^statsig", "Feature flags", "feature-flags"),
    (r"^bullmq$|^bull$|^celery$|^inngest$|^@trigger\.dev/|^node-cron$|^agenda$|^apscheduler$|^sidekiq$|^rq$|^dramatiq$", "Jobs", "jobs"),
    (r"^contentful$|^@sanity/|^sanity$|^@notionhq/client$|^notion-client$|^@prismicio/|^@strapi/", "Content source", "content"),
    (r"^googleapis$|^google-api-python-client$|^@octokit/|^pygithub$|^@linear/sdk$|^plaid$|^react-plaid-link$", "Third-party API", "api"),
]
INTEGRATION_RULES = [(re.compile(pattern), service, kind) for pattern, service, kind in INTEGRATIONS]

# --------------------------------------------------------------------------- surface patterns

_JSX = r"(?<![\w\])])<"
JSX_ROUTE_RE = re.compile(
    _JSX + r"Route\b(?P<attrs>[^>]{0,400}?)\bpath=(?:\"(?P<a>[^\"]*)\"|'(?P<b>[^']*)'|\{\s*[\"'`](?P<c>[^\"'`]*)[\"'`]\s*\})(?P<rest>[^>]{0,300})"
)
JSX_COMPONENT_RE = re.compile(r"(?:element=\{\s*<\s*|[cC]omponent=\{\s*)([A-Z]\w*)")
ROUTER_MARKER_RE = re.compile(
    r"createBrowserRouter|createHashRouter|createMemoryRouter|createRouter\s*\(|RouterModule|"
    r"VueRouter|useRoutes\s*\(|\broutes\s*(?::[^=\n]+)?=\s*\[|RouteRecordRaw|RouteObject|: Routes\b"
)
OBJECT_ROUTE_RE = re.compile(r"\bpath\s*:\s*[\"'`]([^\"'`\n]*)[\"'`](?P<rest>[^{}]{0,240})")
OBJECT_COMPONENT_RE = re.compile(
    r"(?:component|element|Component|lazy|loadComponent)\s*:\s*(?:\(\s*\)\s*=>\s*import\(\s*[\"'][^\"']*?([\w-]+)(?:\.\w+)?[\"']\s*\)|<\s*([A-Z]\w*)|([A-Z]\w*))"
)
NAV_SCREEN_RE = re.compile(
    _JSX + r"\w+\.Screen\b(?P<attrs>[^>]{0,400}?)\bname=(?:\"([^\"]+)\"|'([^']+)')(?P<rest>[^>]{0,300})"
)
NAV_COMPONENT_RE = re.compile(r"component=\{\s*([A-Z]\w*)")
SCREEN_DIR_NAMES = {"pages", "screens", "views", "routes", "scenes"}
SCREEN_DIR_STOP = {
    "components", "component", "hooks", "utils", "lib", "styles", "partials", "widgets",
    "helpers", "store", "stores", "api", "types", "assets", "layouts", "layout", "shared",
    "common", "ui", "context", "contexts", "services",
}
SCREEN_NAME_RE = re.compile(r"^[A-Z]\w*(Screen|Page)\.(tsx|jsx|vue)$")
NATIVE_SCREEN_RE = re.compile(
    r"^(?:[A-Z]\w*(Screen|Page|Activity|Fragment|ViewController)\.(swift|kt|java)|\w+_(screen|page|view)\.dart)$"
)

EXPRESS_RE = re.compile(
    r"\b(?P<recv>app|server|fastify|[A-Za-z_$][\w$]*[Rr]outer|router|routes)\.(?P<verb>get|post|put|patch|delete|all)\(\s*[\"'`](?P<route>/[^\"'`\n]*)[\"'`]"
)
PY_DECORATOR_RE = re.compile(
    r"^\s*@(?P<recv>[\w.]+)\.(?P<verb>route|get|post|put|patch|delete|websocket)\(\s*[\"'](?P<route>[^\"'\n]*)[\"'](?P<rest>[^\n]{0,200})",
    re.MULTILINE,
)
PY_METHODS_RE = re.compile(r"methods\s*=\s*[\[(]([^\])]*)[\])]")
DJANGO_PATH_RE = re.compile(r"\b(?:re_)?path\(\s*r?[\"']([^\"'\n]*)[\"']")
RAILS_ROUTE_RE = re.compile(
    r"^\s*(get|post|put|patch|delete|resources|resource|root|match)\s+[:\"']?([\w/:#.\-]+)", re.MULTILINE
)
GO_ROUTE_RE = re.compile(
    r"\.(HandleFunc|Handle|GET|POST|PUT|PATCH|DELETE|Get|Post|Put|Patch|Delete)\(\s*\"(/[^\"\n]*)\""
)
NEST_CONTROLLER_RE = re.compile(r"@Controller\(\s*(?:[\"'`]([^\"'`]*)[\"'`])?")
NEST_METHOD_RE = re.compile(r"@(Get|Post|Put|Patch|Delete)\(\s*(?:[\"'`]([^\"'`]*)[\"'`])?\s*\)")
HTTP_EXPORT_RE = re.compile(
    r"export\s+(?:async\s+)?(?:function|const)\s+(GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)\b"
)
TRPC_MARKER_RE = re.compile(r"initTRPC|createTRPCRouter|\bt\.router\(|\brouter\(\s*\{")
TRPC_PROC_RE = re.compile(r"^\s*(\w+)\s*:\s*\w*[pP]rocedure\b", re.MULTILINE)
USE_SERVER_RE = re.compile(r"^\s*(?:(?://[^\n]*|/\*.*?\*/)\s*)*[\"']use server[\"']", re.DOTALL)
SERVER_ACTION_RE = re.compile(r"^export\s+(?:async\s+)?(?:function\s+(\w+)|const\s+(\w+)\s*=)", re.MULTILINE)
CONVEX_RE = re.compile(
    r"^export\s+const\s+(\w+)\s*=\s*(query|mutation|action|httpAction)\(", re.MULTILINE
)
CLOUD_FN_RE = re.compile(
    r"export\s+const\s+(\w+)\s*=\s*(?:[\w.]+\.)?(onRequest|onCall|onSchedule|onDocument\w+)\("
)
GRAPHQL_ROOT_RE = re.compile(r"\btype\s+(Query|Mutation)\s*\{([^}]*)\}", re.DOTALL)
GRAPHQL_FIELD_RE = re.compile(r"^\s*(\w+)\s*[(:]", re.MULTILINE)

ARGPARSE_RE = re.compile(r"\.add_parser\(\s*[\"']([\w-]+)[\"']")
CLICK_RE = re.compile(
    r"^\s*@(?P<recv>[\w.]+)\.(?P<kind>command|group)\((?P<args>[^\n]*)\)?\s*$", re.MULTILINE
)
CLICK_NAME_RE = re.compile(r"(?:^|name\s*=\s*)[\"']([\w:-]+)[\"']")
PY_DEF_RE = re.compile(r"^\s*(?:async\s+)?def\s+(\w+)", re.MULTILINE)
JS_COMMAND_RE = re.compile(r"\.command\(\s*[\"'`]([\w:-]+)[^\"'`\n]*[\"'`]")
COBRA_RE = re.compile(r"\bUse:\s*\"([\w-]+)")
CLAP_ENUM_RE = re.compile(r"#\[derive\([^)]*\bSubcommand\b[^)]*\)\][^{;]*?\benum\s+\w+\s*\{", re.DOTALL)
CLAP_VARIANT_RE = re.compile(r"^\s{0,8}([A-Z]\w*)\s*(?:[,({]|$)", re.MULTILINE)
CLI_OPTION_RE = re.compile(
    r"(?:add_argument|\.option|\.requiredOption|click\.option|typer\.Option)\(\s*(?:[\"'`]-\w[\"'`]\s*,\s*)?[\"'`](--[\w-]+)"
)

PRISMA_MODEL_RE = re.compile(r"^model\s+(\w+)\s*\{", re.MULTILINE)
DJANGO_MODEL_RE = re.compile(r"^class\s+(\w+)\(\s*(?:[\w.]+,\s*)*models\.Model\b", re.MULTILINE)
TABLENAME_RE = re.compile(r"__tablename__\s*=\s*[\"'](\w+)[\"']")
SQLMODEL_RE = re.compile(r"^class\s+(\w+)\([^)]*\btable\s*=\s*True", re.MULTILINE)
SQL_TABLE_RE = re.compile(
    r"\bCREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?[\"`\[]?(?:\w+[\"`\]]?\.[\"`\[]?)?(\w+)", re.IGNORECASE
)
DRIZZLE_RE = re.compile(r"\b(?:pg|mysql|sqlite)Table\(\s*[\"'`](\w+)[\"'`]")
ENTITY_RE = re.compile(r"@Entity\b[^\n]*\n(?:\s*@[^\n]*\n)*\s*(?:export\s+|public\s+|data\s+|open\s+|abstract\s+)*class\s+(\w+)")
MONGOOSE_RE = re.compile(r"\bmodel(?:<[^>]*>)?\(\s*[\"'`](\w+)[\"'`]\s*,")
SEQUELIZE_RE = re.compile(r"\.define\(\s*[\"'`](\w+)[\"'`]\s*,\s*\{")
RAILS_TABLE_RE = re.compile(r"\bcreate_table\s+[:\"'](\w+)")
SWIFTDATA_RE = re.compile(r"@Model\s+(?:final\s+)?class\s+(\w+)")
CONVEX_TABLE_RE = re.compile(r"^\s*(\w+)\s*:\s*defineTable\(", re.MULTILINE)
FIRESTORE_RE = re.compile(r"\bcollection\(\s*(?:\w+\s*,\s*)?[\"'`]([A-Za-z][\w-]*)[\"'`]\s*\)")

ENV_ACCESS_RE = re.compile(
    r"process\.env\.([A-Z][A-Z0-9_]+)|process\.env\[[\"']([A-Z][A-Z0-9_]+)[\"']\]|"
    r"import\.meta\.env\.([A-Z][A-Z0-9_]+)|os\.environ(?:\.get)?[\[(]\s*[\"']([A-Z][A-Z0-9_]+)[\"']|"
    r"os\.getenv\(\s*[\"']([A-Z][A-Z0-9_]+)[\"']|ENV\[[\"']([A-Z][A-Z0-9_]+)[\"']\]|"
    r"Deno\.env\.get\(\s*[\"']([A-Z][A-Z0-9_]+)[\"']|env::var\(\s*\"([A-Z][A-Z0-9_]+)\"|"
    r"os\.Getenv\(\s*\"([A-Z][A-Z0-9_]+)\""
)
FLAG_NAME_RE = re.compile(
    r"^(?:NEXT_PUBLIC_|VITE_|EXPO_PUBLIC_|REACT_APP_|PUBLIC_)?(?:(?:FEATURE|FF|FLAG|ENABLE|DISABLE|SHOW|HIDE|ALLOW|USE|EXPERIMENTAL|BETA)_[A-Z0-9_]+|[A-Z0-9_]+_(?:ENABLED|DISABLED|FLAG|BETA))$"
)
PREFERENCE_KEY_RES = [
    re.compile(r"\b(?:localStorage|sessionStorage)\.(?:setItem|getItem)\(\s*[\"'`]([\w.:@/-]+)[\"'`]"),
    re.compile(r"\bAsyncStorage\.(?:setItem|getItem)\(\s*[\"'`]([\w.:@/-]+)[\"'`]"),
    re.compile(r"\buseLocalStorage(?:<[^>]*>)?\(\s*[\"'`]([\w.:@/-]+)[\"'`]"),
    re.compile(r"\bprefs?\.(?:set|get)(?:Bool|String|Int|Double|StringList)\(\s*[\"']([\w.:-]+)[\"']"),
    re.compile(r"\bforKey:\s*\"([\w.:-]+)\""),
    re.compile(r"@AppStorage\(\s*\"([\w.:-]+)\""),
]
SETTINGS_PATH_RE = re.compile(r"settings?|preferences?|prefs|options", re.IGNORECASE)
NOT_A_PREFERENCE_RE = re.compile(r"token|auth|session|jwt|refresh|credential|password|secret|cache|csrf|nonce", re.IGNORECASE)
NAV_NAME_RE = re.compile(
    r"(^|[-_.])(nav|navbar|navigation|navigator|sidebar|menu|tabbar|tabs|header|footer|drawer|"
    r"appshell|shell|topbar|primarybuttons)([-_.]|$)|nav(bar|igation|igator)?$|sidebar|tabbar|"
    r"^[_+]?layout$",
    re.IGNORECASE,
)
# A link, nav-table entry, or programmatic navigation that names an in-app destination.
LINK_TARGET_RE = re.compile(
    r"(?:\b(?:to|href)=\{?\s*[\"'`]|\b(?:href|to|url|route|link)\s*:\s*[\"'`]|"
    r"\b(?:navigate|push|replace|goto|redirect)\(\s*[\"'`])(/[\w\-/\[\]:.]*)"
)
PATH_KEY_TARGET_RE = re.compile(r"\bpath\s*:\s*[\"'`](/[\w\-/\[\]:.]*)")
NOT_A_DESTINATION_RE = re.compile(r"^/(api|static|assets|_next|public|images?|img|fonts?|favicon)(/|$)|\.[A-Za-z0-9]{2,5}$")
GENERATED_FILE_RE = re.compile(r"\.gen\.|\.generated\.|(^|/)(generated|__generated__|gen)/")
NAV_ITEM_RE = re.compile(
    _JSX + r"\w+\.Screen\b|\b(?:BottomNavigationBarItem|NavigationDestination|NavigationRailDestination|TabItem)\("
)
BOOKKEEPING_TABLE_RE = re.compile(
    r"^_|migrations?$|^db_version$|^alembic_version$|^flyway_schema_history$|^sqlite_sequence$|"
    r"^ar_internal_metadata$|^knex_|^(if|not|exists)$",
    re.IGNORECASE,
)
ORM_KINDS = {
    "prisma", "django", "sqlalchemy", "sqlmodel", "drizzle", "entity", "mongoose", "sequelize",
    "rails", "swiftdata", "convex",
}
PY_PREFIX_RE = re.compile(
    r"^\s*(\w+)\s*=\s*(?:\w+\.)?(?:APIRouter|Blueprint)\((?P<args>[^)]*)\)", re.MULTILINE
)
PY_PREFIX_ARG_RE = re.compile(r"\b(?:url_)?prefix\s*=\s*[\"']([^\"']*)[\"']")
NOT_A_SCREEN_STEMS = {
    "utils", "hooks", "styles", "types", "constants", "helpers", "context", "store", "api",
    "layout", "loading", "error", "not-found", "template", "provider", "providers", "theme",
}
ENTRY_SCREEN_STEMS = {"MainActivity", "AppDelegate", "SceneDelegate", "MainApplication"}
FILE_ROUTER_OWNS = {
    "routes": {"sveltekit", "remix", "tanstack-router"},
    "pages": {"next", "nuxt", "astro"},
}

MARKUP_CONTROLS = {
    "toggles": re.compile(_JSX + r"(?:Switch|Toggle|Checkbox|Radio|RadioGroupItem)\b|type=[\"'](?:checkbox|radio)[\"']"),
    "choices": re.compile(_JSX + r"(?:Select|select|Dropdown|DropdownMenu|RadioGroup|Picker|Combobox|Slider|SegmentedControl)\b"),
    "inputs": re.compile(_JSX + r"(?:input|Input|TextInput|textarea|Textarea|TextField|TextArea|DatePicker|NumberInput)\b(?![^>]*type=[\"'](?:checkbox|radio|hidden|submit|button)[\"'])"),
    "buttons": re.compile(_JSX + r"(?:button|Button|Pressable|TouchableOpacity|IconButton|TouchableHighlight|Fab)\b"),
    "overlays": re.compile(_JSX + r"(?:Modal|Dialog|Drawer|Sheet|Popover|AlertDialog|BottomSheet|Tooltip|ContextMenu)\b"),
    "tabs": re.compile(_JSX + r"(?:Tabs|TabsTrigger|TabPanel|Tab)\b"),
}
NATIVE_CONTROLS = {
    "toggles": re.compile(r"\b(?:Switch|SwitchListTile|Checkbox|CheckboxListTile|Radio|RadioListTile|RadioButton|Toggle)\("),
    "choices": re.compile(r"\b(?:DropdownButton\w*|PopupMenuButton|Picker|DropdownMenu|Slider|SegmentedButton)\b[(<]"),
    "inputs": re.compile(r"\b(?:TextField|TextFormField|SecureField|TextEditor|OutlinedTextField)\("),
    "buttons": re.compile(r"\b(?:ElevatedButton|TextButton|OutlinedButton|IconButton|FloatingActionButton|FilledButton|Button)\("),
    "overlays": re.compile(r"\bshow(?:Dialog|ModalBottomSheet|BottomSheet)\(|\.(?:sheet|alert|popover|fullScreenCover|confirmationDialog)\(|\b(?:AlertDialog|ModalBottomSheet)\("),
    "tabs": re.compile(r"\b(?:TabBar|TabView|TabRow|Tab)\("),
}

UNFINISHED_RE = re.compile(
    r"coming soon|not (?:yet )?implemented|under construction|work in progress|lorem ipsum|"
    r"placeholder (?:page|screen|content|view)",
    re.IGNORECASE,
)
TODO_RE = re.compile(r"\b(TODO|FIXME|HACK|XXX)\b")
PATH_LITERAL_RE = re.compile(r"[\"'`](/[A-Za-z0-9_\-./\[\]:$]*)")
WORD_LITERAL_RE = re.compile(r"[\"'`]([A-Za-z][\w-]{1,60})[\"'`]")
IMPORT_RE = re.compile(r"(?:\bfrom\s+|\bimport\s*\(\s*|\brequire\s*\(\s*|^\s*import\s+)[\"']([^\"'\n]+)[\"']", re.MULTILINE)
SPECIAL_ROUTE_RE = re.compile(
    r"callback|oauth|webhook|verify|reset|confirm|unsubscribe|invite|share|embed|404|500|"
    r"not-found|notfound|error|offline|sitemap|robots|rss|feed|opengraph|manifest|"
    r"^/api(?:/|$)|^/_|\*",
    re.IGNORECASE,
)

REPORT_SECTIONS = [
    "Promise", "Snapshot", "Features", "Complexity", "Direction", "Outside view",
    "Next moves", "History",
]
SNAPSHOT_MEASURES = [
    "Features", "Core", "Supporting", "Adjacent", "Off-promise", "Screens", "Endpoints",
    "Commands", "Data models", "Packages", "Settings and flags", "Integrations",
    "Top-level destinations", "Steps to the core action",
]
FEATURE_CLASSES = ["core", "supporting", "adjacent", "off-promise"]
FEATURE_COSTS = ["light", "moderate", "heavy"]
VERDICTS = ["keep", "finish", "simplify", "merge", "park", "cut"]
DIRECTION_VERDICTS = ["focused", "drifting", "split", "undefined"]
DECIDERS = {"audit", "owner", "owner-delegated"}
NOTHING_NEXT = "nothing obvious; next is whatever you decide to build."


# --------------------------------------------------------------------------- utilities


def fail(message: str, code: int = 1) -> NoReturn:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(code)


def authorized_root(path: str) -> Path:
    root = Path(os.path.abspath(os.path.expanduser(path)))
    if not root.is_dir():
        fail(f"root is not a directory: {root}")
    return root


def clip(text: str, limit: int = TEXT_CLIP) -> str:
    return " ".join(text.split())[:limit]


def cap(items: list, limit: int = MAX_LIST) -> dict:
    return {"items": items[:limit], "truncated": len(items) > limit, "total": len(items)}


def is_env_file(name: str) -> bool:
    return name == ".env" or name.startswith(".env.") or name.endswith(".env")


def is_text_candidate(path: Path) -> bool:
    if is_env_file(path.name):
        return False
    return path.suffix.lower() in TEXT_SUFFIXES or path.name in BARE_TEXT_NAMES


def read_text(path: Path) -> str | None:
    try:
        if path.is_symlink() or path.stat().st_size > MAX_CONTENT_BYTES:
            return None
        data = path.read_bytes()
    except OSError:
        return None
    if b"\x00" in data[:4096]:
        return None
    return data.decode("utf-8", errors="replace")


def git(root: Path, *args: str) -> str | None:
    try:
        completed = subprocess.run(
            ["git", "-c", "core.quotepath=off", *args],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
            env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"},
        )
    except OSError:
        return None
    if completed.returncode != 0:
        return None
    return completed.stdout


def walk(root: Path) -> tuple[list[str], bool]:
    files: list[str] = []
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        for name in sorted(filenames):
            path = Path(dirpath) / name
            if path.is_symlink() or not path.is_file():
                continue
            files.append(path.relative_to(root).as_posix())
            if len(files) >= MAX_FILES:
                return files, True
    return files, False


def line_of(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def is_non_product(relative: str, product_roots: frozenset[str] = frozenset()) -> bool:
    """True for tests, examples, documentation, and developer tooling.

    A directory in `product_roots` (an agent skill, whose scripts and references are what it
    ships) is judged by where it sits, not by the names of the folders inside it.
    """
    parts = relative.split("/")
    for depth in range(len(parts) - 1, 0, -1):
        if "/".join(parts[:depth]) in product_roots:
            parts = parts[:depth] + [parts[-1]]
            break
    if any(part.lower() in NON_PRODUCT_DIRS for part in parts[:-1]):
        return True
    return bool(TEST_FILE_RE.search(parts[-1]))


def normalize_dep(name: str) -> str:
    return name.strip().lower().replace("_", "-")


def quarter_of(date: str) -> str:
    return f"{date[:4]}-Q{(int(date[5:7]) - 1) // 3 + 1}"


# --------------------------------------------------------------------------- git history


def git_history(root: Path, window_days: int) -> dict:
    """One pass over history: when each file arrived, how often it changed, and how recently.

    Renames carry the original arrival date forward, so a moved screen is not counted as new.
    Dates are compared to HEAD's commit date rather than the wall clock, which keeps the
    result reproducible for a given commit.
    """
    history: dict = {"available": False}
    if git(root, "rev-parse", "--is-inside-work-tree") is None:
        return history
    head = git(root, "log", "-1", "--format=%H%x09%ad", "--date=short")
    if not head or "\t" not in head:
        return history
    head_sha, head_date_raw = head.strip().split("\t", 1)
    try:
        head_date = dt.date.fromisoformat(head_date_raw)
    except ValueError:
        return history
    raw = git(
        root, "log", "--no-merges", "--reverse", "-M", "--relative", "--name-status",
        "--date=short", "--format=@%H%x09%ad%x09%s",
    )
    if raw is None:
        return history
    cutoff = head_date - dt.timedelta(days=window_days)
    added: dict[str, str] = {}
    last: dict[str, str] = {}
    commits: Counter[str] = Counter()
    recent: Counter[str] = Counter()
    dir_commits: Counter[str] = Counter()
    dir_recent: Counter[str] = Counter()
    by_quarter: Counter[str] = Counter()
    total = recent_total = 0
    first_date = None
    current_date = None
    is_recent = False
    touched_dirs: set[str] = set()
    commit_dates: dict[str, str] = {}
    recent_log: list[dict] = []
    current_subject = ""
    touched_leaves: Counter[str] = Counter()

    def flush() -> None:
        for directory in touched_dirs:
            dir_commits[directory] += 1
            if is_recent:
                dir_recent[directory] += 1
        if is_recent and current_date is not None and (touched_leaves or current_subject):
            entry = {
                "date": current_date,
                "subject": clip(current_subject, 100),
                "touched": sorted(name for name, _ in touched_leaves.most_common(MAX_TOUCHED)),
            }
            if len(touched_leaves) > MAX_TOUCHED:
                entry["more_places"] = len(touched_leaves) - MAX_TOUCHED
            recent_log.append(entry)
        touched_dirs.clear()
        touched_leaves.clear()

    for line in raw.splitlines():
        if not line:
            continue
        if line.startswith("@"):
            flush()
            parts = line[1:].split("\t", 2)
            current_date = parts[1] if len(parts) > 1 else None
            current_subject = parts[2] if len(parts) > 2 else ""
            if current_date is None:
                continue
            commit_dates[parts[0]] = current_date
            first_date = first_date or current_date
            try:
                is_recent = dt.date.fromisoformat(current_date) >= cutoff
            except ValueError:
                is_recent = False
            total += 1
            recent_total += int(is_recent)
            by_quarter[quarter_of(current_date)] += 1
            continue
        if current_date is None:
            continue
        fields = line.split("\t")
        status = fields[0]
        if status.startswith(("R", "C")) and len(fields) >= 3:
            old, path = fields[1], fields[2]
            origin = added.get(old, current_date)
            if status.startswith("R"):
                added.pop(old, None)
                commits[path] += commits.pop(old, 0)
                recent[path] += recent.pop(old, 0)
                last.pop(old, None)
            added[path] = origin
        elif len(fields) >= 2:
            path = fields[1]
            if status.startswith("D"):
                for table in (added, last, commits, recent):
                    table.pop(path, None)
                continue
            added.setdefault(path, current_date)
        else:
            continue
        commits[path] += 1
        if is_recent:
            recent[path] += 1
        last[path] = current_date
        segments = path.split("/")[:-1]
        for depth in range(1, min(len(segments), 4) + 1):
            touched_dirs.add("/".join(segments[:depth]))
        touched_leaves["/".join(segments[:3]) or "."] += 1
    flush()
    shallow = (git(root, "rev-parse", "--is-shallow-repository") or "").strip() == "true"
    status = git(root, "status", "--porcelain", "--untracked-files=normal", "--", ".") or ""
    dirty = [line for line in status.splitlines() if line.strip() and not line[3:].strip().endswith(SCAN_NAME)]
    history.update(
        {
            "available": True,
            "head": head_sha,
            "head_date": head_date_raw,
            "first_commit_date": first_date,
            "shallow": shallow,
            "uncommitted": {
                "modified": sum(1 for line in dirty if not line.startswith("??")),
                "untracked": sum(1 for line in dirty if line.startswith("??")),
            },
            "window_days": window_days,
            "commits": total,
            "recent_commits": recent_total,
            "commits_by_quarter": dict(sorted(by_quarter.items())),
            "_added": added,
            "_last": last,
            "_commits": commits,
            "_recent": recent,
            "_dir_commits": dir_commits,
            "_dir_recent": dir_recent,
            "_commit_dates": commit_dates,
            "_recent_log": recent_log[::-1],
        }
    )
    return history


MAX_TOUCHED = 10
BLAME_HEADER_RE = re.compile(r"^([0-9a-f]{40}) \d+ (\d+)(?: \d+)?$")
MAX_BLAMED_FILES = 60


def line_dates(root: Path, path: str, history: dict) -> dict[int, str | None]:
    """Map each line of a file to the day it was last changed, for items that share a file."""
    raw = git(root, "blame", "--porcelain", "--", path)
    if raw is None:
        return {}
    known: dict[str, str] = dict(history.get("_commit_dates", {}))
    owner: dict[int, str] = {}
    current = None
    for line in raw.splitlines():
        header = BLAME_HEADER_RE.match(line)
        if header:
            current = header.group(1)
            owner[int(header.group(2))] = current
        elif line.startswith("author-time ") and current is not None and current not in known:
            try:
                moment = dt.datetime.fromtimestamp(int(line.split()[1]), dt.timezone.utc)
            except (ValueError, OverflowError, OSError):
                continue
            known[current] = moment.date().isoformat()
    # An all-zero commit id marks a line that is not committed yet.
    return {number: (None if set(sha) == {"0"} else known.get(sha)) for number, sha in owner.items()}


def date_shared_items(root: Path, history: dict, groups: list[list[dict]]) -> None:
    """Items that share a file get the date of their own defining line, not the file's."""
    if not history.get("available"):
        return
    by_path: dict[str, list[dict]] = {}
    for group in groups:
        for item in group:
            if "line" in item:
                by_path.setdefault(item["path"], []).append(item)
    shared = sorted(path for path, items in by_path.items() if len(items) > 1)[:MAX_BLAMED_FILES]
    for path in shared:
        dates = line_dates(root, path, history)
        if not dates:
            continue
        for item in by_path[path]:
            item["added"] = dates.get(item["line"])
            item["dated_by"] = "line"
            for key in ("last_touched", "commits", "recent_commits"):
                item.pop(key, None)  # those describe the whole file, not this item


def stamp(item: dict, history: dict) -> dict:
    """Attach arrival and activity facts for the file an item lives in."""
    if history.get("available"):
        path = item["path"]
        item["added"] = history["_added"].get(path)
        item["last_touched"] = history["_last"].get(path)
        item["commits"] = history["_commits"].get(path, 0)
        item["recent_commits"] = history["_recent"].get(path, 0)
    return item


# --------------------------------------------------------------------------- manifests


def _toml(text: str) -> dict:
    if tomllib is None:
        return {}
    try:
        return tomllib.loads(text)
    except (tomllib.TOMLDecodeError, ValueError):
        return {}


def _requirement_name(spec: str) -> str | None:
    match = re.match(r"\s*([A-Za-z0-9][A-Za-z0-9._-]*)", spec)
    return match.group(1) if match else None


def load_manifests(contents: dict[str, str]) -> list[dict]:
    manifests: list[dict] = []
    for relative, text in sorted(contents.items()):
        name = relative.rsplit("/", 1)[-1]
        depth = relative.count("/")
        if depth > 4:
            continue
        entry: dict | None = None
        if name == "package.json":
            try:
                data = json.loads(text)
            except json.JSONDecodeError:
                continue
            if not isinstance(data, dict):
                continue
            deps = data.get("dependencies") if isinstance(data.get("dependencies"), dict) else {}
            dev = data.get("devDependencies") if isinstance(data.get("devDependencies"), dict) else {}
            bins = data.get("bin")
            if isinstance(bins, str):
                bins = {str(data.get("name", "")).split("/")[-1]: bins}
            entry = {
                "runtime": sorted(deps), "dev": sorted(dev),
                "description": data.get("description") if isinstance(data.get("description"), str) else None,
                "bins": sorted(bins) if isinstance(bins, dict) else [],
                "name": data.get("name") if isinstance(data.get("name"), str) else None,
            }
        elif name == "pyproject.toml":
            data = _toml(text)
            project = data.get("project") if isinstance(data.get("project"), dict) else {}
            poetry = data.get("tool", {}).get("poetry", {}) if isinstance(data.get("tool"), dict) else {}
            runtime = [_requirement_name(d) for d in project.get("dependencies", []) if isinstance(d, str)]
            if isinstance(poetry.get("dependencies"), dict):
                runtime += [k for k in poetry["dependencies"] if k.lower() != "python"]
            optional: list[str | None] = []
            if isinstance(project.get("optional-dependencies"), dict):
                for group in project["optional-dependencies"].values():
                    optional += [_requirement_name(d) for d in group if isinstance(d, str)]
            scripts = {}
            for source in (project.get("scripts"), poetry.get("scripts")):
                if isinstance(source, dict):
                    scripts.update(source)
            if not data:
                runtime = re.findall(r"^\s*[\"']([A-Za-z0-9][A-Za-z0-9._-]*)", text, re.MULTILINE)
            entry = {
                "runtime": sorted({d for d in runtime if d}), "dev": sorted({d for d in optional if d}),
                "description": project.get("description") or poetry.get("description"),
                "bins": sorted(scripts),
                "name": project.get("name") or poetry.get("name"),
            }
        elif re.fullmatch(r"requirements[\w.-]*\.txt", name):
            runtime = [
                _requirement_name(line) for line in text.splitlines()
                if line.strip() and not line.lstrip().startswith(("#", "-"))
            ]
            entry = {"runtime": sorted({d for d in runtime if d}), "dev": [], "description": None, "bins": []}
        elif name == "go.mod":
            runtime = [
                m.group(1) for m in re.finditer(r"^\s*(?:require\s+)?([\w./-]+\.[\w./-]+)\s+v\d[^\n]*$", text, re.MULTILINE)
                if "// indirect" not in m.group(0)
            ]
            entry = {"runtime": sorted(set(runtime)), "dev": [], "description": None, "bins": []}
        elif name == "Cargo.toml":
            data = _toml(text)
            package = data.get("package") if isinstance(data.get("package"), dict) else {}
            deps = data.get("dependencies") if isinstance(data.get("dependencies"), dict) else {}
            entry = {
                "runtime": sorted(deps), "dev": [],
                "description": package.get("description") if isinstance(package.get("description"), str) else None,
                "bins": [], "name": package.get("name") if isinstance(package.get("name"), str) else None,
            }
        elif name == "Gemfile":
            entry = {
                "runtime": sorted(set(re.findall(r"^\s*gem\s+[\"']([\w-]+)[\"']", text, re.MULTILINE))),
                "dev": [], "description": None, "bins": [],
            }
        elif name == "pubspec.yaml":
            runtime: list[str] = []
            block = None
            for line in text.splitlines():
                top = re.match(r"^(\w[\w_]*):", line)
                if top:
                    block = top.group(1)
                    continue
                dep = re.match(r"^  ([A-Za-z_][\w]*):", line)
                if dep and block == "dependencies":
                    runtime.append(dep.group(1))
            description = re.search(r"^description:\s*[\"']?(.+?)[\"']?\s*$", text, re.MULTILINE)
            declared = re.search(r"^name:\s*[\"']?([\w-]+)", text, re.MULTILINE)
            entry = {
                "runtime": sorted(set(runtime)), "dev": [],
                "description": description.group(1) if description else None, "bins": [],
                "name": declared.group(1) if declared else None,
            }
        elif name == "composer.json":
            try:
                data = json.loads(text)
            except json.JSONDecodeError:
                continue
            require = data.get("require") if isinstance(data, dict) and isinstance(data.get("require"), dict) else {}
            entry = {
                "runtime": sorted(k for k in require if k != "php" and not k.startswith("ext-")),
                "dev": [], "description": data.get("description") if isinstance(data, dict) else None, "bins": [],
                "name": data.get("name") if isinstance(data, dict) and isinstance(data.get("name"), str) else None,
            }
        elif name == "Podfile":
            entry = {
                "runtime": sorted(set(re.findall(r"^\s*pod\s+[\"']([\w/+-]+)[\"']", text, re.MULTILINE))),
                "dev": [], "description": None, "bins": [],
            }
        elif name in {"build.gradle", "build.gradle.kts"}:
            runtime = re.findall(r"\b(?:implementation|api)\s*\(?\s*[\"']([\w.-]+:[\w.-]+)", text)
            entry = {"runtime": sorted(set(runtime)), "dev": [], "description": None, "bins": []}
        if entry is not None:
            entry["path"] = relative
            entry.setdefault("name", None)
            manifests.append(entry)
    return manifests


FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*(?:\n|\Z)", re.DOTALL)


def _frontmatter_value(block: str, key: str) -> str | None:
    match = re.search(rf"^{re.escape(key)}:\s*(.*)$", block, re.MULTILINE)
    if not match:
        return None
    value = match.group(1).strip()
    if value in {">", "|", ">-", "|-", ">+", "|+"}:
        lines = []
        for line in block[match.end():].splitlines()[1:]:
            if line and not line[0].isspace():
                break
            lines.append(line.strip())
        value = " ".join(lines)
    return value.strip("\"'") or None


def detect_packages(contents: dict[str, str], manifests: list[dict]) -> list[dict]:
    """Installable units a product is made of: workspace packages, plugins, and agent skills."""
    packages: list[dict] = []
    for manifest in manifests:
        path = manifest["path"]
        if "/" not in path or is_non_product(path) or not manifest.get("name"):
            continue
        if path.rsplit("/", 1)[-1] in {"package.json", "pyproject.toml", "Cargo.toml", "pubspec.yaml", "composer.json"}:
            entry = {"name": manifest["name"], "kind": "package", "path": path}
            if manifest.get("description"):
                entry["description"] = clip(str(manifest["description"]), 200)
            packages.append(entry)
    for relative, text in sorted(contents.items()):
        name = relative.rsplit("/", 1)[-1]
        is_plugin_manifest = relative.endswith("/.claude-plugin/plugin.json")
        owner_parts = relative.split("/")[:-2] if is_plugin_manifest else relative.split("/")[:-1]
        if is_non_product(relative) or any(part.startswith(".") for part in owner_parts):
            continue  # hidden directories hold the developer's own tooling, not the product
        if is_plugin_manifest and owner_parts:
            try:
                data = json.loads(text)
            except json.JSONDecodeError:
                continue
            if isinstance(data, dict) and isinstance(data.get("name"), str):
                entry = {"name": data["name"], "kind": "plugin", "path": relative}
                if isinstance(data.get("description"), str):
                    entry["description"] = clip(data["description"], 200)
                packages.append(entry)
        elif name == "SKILL.md" and "/" in relative:
            front = FRONTMATTER_RE.match(text)
            block = front.group(1) if front else ""
            entry = {
                "name": _frontmatter_value(block, "name") or relative.split("/")[-2],
                "kind": "agent-skill", "path": relative,
                "user_invoked": (_frontmatter_value(block, "disable-model-invocation") or "").lower() == "true",
            }
            hint = _frontmatter_value(block, "argument-hint")
            if hint:
                entry["argument_hint"] = clip(hint, 120)
            description = _frontmatter_value(block, "description")
            if description:
                entry["description"] = clip(description, 200)
            packages.append(entry)
    plugin_roots = {
        package["path"][: -len("/.claude-plugin/plugin.json")]: package
        for package in packages if package["kind"] == "plugin"
    }
    for plugin_root, plugin in plugin_roots.items():
        plugin["has_hooks"] = f"{plugin_root}/hooks/hooks.json" in contents
    for package in packages:
        if package["kind"] == "agent-skill":
            owner = next((root for root in plugin_roots if package["path"].startswith(root + "/")), None)
            if owner is not None:
                package["plugin"] = plugin_roots[owner]["name"]
    return packages


def detect_integrations(manifests: list[dict]) -> list[dict]:
    found: dict[tuple[str, str], dict] = {}
    for manifest in manifests:
        for dependency in manifest["runtime"] + manifest["dev"]:
            normalized = normalize_dep(dependency)
            for pattern, service, kind in INTEGRATION_RULES:
                if pattern.search(normalized):
                    key = (service, kind)
                    entry = found.setdefault(
                        key, {"service": service, "kind": kind, "dependencies": [], "manifests": []}
                    )
                    if dependency not in entry["dependencies"]:
                        entry["dependencies"].append(dependency)
                    if manifest["path"] not in entry["manifests"]:
                        entry["manifests"].append(manifest["path"])
                    break
    return sorted(found.values(), key=lambda item: (item["kind"], item["service"]))


def detect_stack(manifests: list[dict], relatives: list[str]) -> list[str]:
    stack: set[str] = set()
    for manifest in manifests:
        for dependency in manifest["runtime"] + manifest["dev"]:
            normalized = normalize_dep(dependency)
            label = STACK_MARKERS.get(normalized) or STACK_MARKERS.get(dependency)
            if label:
                stack.add(label)
            elif normalized.startswith("github.com/"):
                for marker, name in STACK_MARKERS.items():
                    if marker.startswith("github.com/") and normalized.startswith(marker):
                        stack.add(name)
    names = {relative.rsplit("/", 1)[-1] for relative in relatives}
    if "manage.py" in names:
        stack.add("django")
    if any(relative.endswith("config/routes.rb") for relative in relatives):
        stack.add("rails")
    if any(relative.endswith(".xcodeproj/project.pbxproj") or relative.endswith("Package.swift") for relative in relatives):
        stack.add("swift")
    if "AndroidManifest.xml" in names:
        stack.add("android")
    return sorted(stack)


# --------------------------------------------------------------------------- purpose


IMAGE_RE = re.compile(r"!\[([^\]]*)\]\([^)]*\)")
EMPTY_LINK_RE = re.compile(r"\[\s*\]\([^)]*\)")
HTML_HEADING_RE = re.compile(r"<h([1-6])[^>]*>(.*?)</h\1>", re.IGNORECASE | re.DOTALL)
ABOUT_HEADING_RE = re.compile(r"^#{2,3}\s+(about|overview|what is\b.*|introduction|description|why\b.*)\s*$", re.IGNORECASE)


def _first_sentence_block(blocks: list[str]) -> str | None:
    for block in blocks:
        stripped = re.sub(r"^(?:>\s*)+", "", block.strip()).lstrip("#").strip()
        stripped = EMPTY_LINK_RE.sub("", IMAGE_RE.sub("", stripped)).strip()
        if stripped and not stripped.startswith(("[!", "|", "```", "- ", "* ", "+ ")) and len(stripped.split()) >= 6:
            return clip(stripped)
    return None


def readme_purpose(text: str) -> tuple[str | None, str | None]:
    """Title plus the opening statement: the first real sentence between the title and the

    first section, or the first sentence of an About-style section. Anything further down is
    setup, not purpose.
    """
    text = HTML_HEADING_RE.sub(
        lambda m: "\n" + "#" * int(m.group(1)) + " " + HTML_TAG_RE.sub("", m.group(2)).strip() + "\n", text
    )
    lines = HTML_TAG_RE.sub(" ", text).splitlines()
    headings = [index for index, line in enumerate(lines) if HEADING_RE.match(line)]
    top = next((index for index in headings[:6] if lines[index].startswith("# ")), None)
    title_index = top if top is not None else (headings[0] if headings else None)
    title = None
    start = 0
    if title_index is not None:
        title = IMAGE_RE.sub(r"\1", lines[title_index].lstrip("#")).strip() or None
        start = title_index + 1
    intro: list[str] = []
    for line in lines[start:]:
        if HEADING_RE.match(line) and not line.lstrip("#").strip().startswith(">"):
            break
        intro.append(line)
    paragraph = _first_sentence_block(re.split(r"\n\s*\n", "\n".join(intro)))
    if paragraph is None:
        for index, line in enumerate(lines):
            if ABOUT_HEADING_RE.match(line):
                section: list[str] = []
                for following in lines[index + 1:]:
                    if HEADING_RE.match(following):
                        break
                    section.append(following)
                paragraph = _first_sentence_block(re.split(r"\n\s*\n", "\n".join(section)))
                if paragraph:
                    break
    return title, paragraph


def purpose_sources(contents: dict[str, str], manifests: list[dict]) -> list[dict]:
    sources: list[dict] = []
    readmes = sorted(r for r in contents if README_RE.match(r.rsplit("/", 1)[-1]) and r.count("/") <= 1)
    root_readmes = [r for r in readmes if "/" not in r]
    for relative in root_readmes or [r for r in readmes if not is_non_product(r)][:3]:
        title, paragraph = readme_purpose(contents[relative])
        sources.append({"path": relative, "kind": "readme", "title": title, "opening": paragraph})
    for manifest in manifests:
        if manifest.get("description") and manifest["path"].count("/") <= 2:
            sources.append({"path": manifest["path"], "kind": "manifest", "description": clip(str(manifest["description"]))})
    for relative in (".claude-plugin/marketplace.json", ".claude-plugin/plugin.json"):
        try:
            data = json.loads(contents.get(relative, ""))
        except json.JSONDecodeError:
            continue
        nested = data.get("metadata") if isinstance(data, dict) and isinstance(data.get("metadata"), dict) else {}
        description = (data.get("description") if isinstance(data, dict) else None) or nested.get("description")
        if isinstance(description, str) and description.strip():
            sources.append({"path": relative, "kind": "manifest", "description": clip(description)})
    for relative in sorted(contents):
        if is_non_product(relative) or relative.count("/") > 4:
            continue
        name = relative.rsplit("/", 1)[-1]
        text = contents[relative]
        if name in {"manifest.json", "site.webmanifest", "manifest.webmanifest", "app.json"}:
            try:
                data = json.loads(text)
            except json.JSONDecodeError:
                continue
            if not isinstance(data, dict):
                continue
            node = data.get("expo") if isinstance(data.get("expo"), dict) else data
            facts = {k: clip(str(node[k])) for k in ("name", "short_name", "description") if isinstance(node.get(k), str)}
            if facts.get("description") or (name != "app.json" and facts):
                sources.append({"path": relative, "kind": "app-manifest", **facts})
        elif name == "index.html":
            title = re.search(r"<title[^>]*>([^<]{3,200})</title>", text, re.IGNORECASE)
            meta = re.search(
                r"<meta[^>]+name=[\"']description[\"'][^>]+content=[\"']([^\"']{3,400})[\"']", text, re.IGNORECASE
            )
            if title or meta:
                sources.append({
                    "path": relative, "kind": "page-metadata",
                    "title": clip(title.group(1)) if title else None,
                    "description": clip(meta.group(1)) if meta else None,
                })
        elif re.fullmatch(r"(layout|_layout|\+layout|app|_app)\.(tsx|jsx|ts|js|svelte)", name) and relative.count("/") <= 3:
            block = re.search(r"\bmetadata\b[^=]*=\s*\{(.{0,600}?)\}", text, re.DOTALL)
            if block:
                title = re.search(r"\btitle\s*:\s*[\"'`]([^\"'`]{3,200})[\"'`]", block.group(1))
                description = re.search(r"\bdescription\s*:\s*[\"'`]([^\"'`]{3,400})[\"'`]", block.group(1))
                if title or description:
                    sources.append({
                        "path": relative, "kind": "page-metadata",
                        "title": clip(title.group(1)) if title else None,
                        "description": clip(description.group(1)) if description else None,
                    })
    return sources


def claimed_features(contents: dict[str, str]) -> list[dict]:
    claims: list[dict] = []
    for relative in sorted(contents):
        name = relative.rsplit("/", 1)[-1]
        if not README_RE.match(name) or relative.count("/") > 1:
            continue
        level = None
        in_code = False
        for number, line in enumerate(contents[relative].splitlines(), start=1):
            if line.lstrip().startswith("```"):
                in_code = not in_code
                continue
            if in_code:
                continue
            heading = HEADING_RE.match(line)
            if heading:
                feature = FEATURE_HEADING_RE.match(line)
                if feature:
                    level = len(feature.group(1))
                elif level is not None and len(heading.group(1)) <= level:
                    level = None
                continue
            if level is None:
                continue
            bullet = BULLET_RE.match(line)
            if bullet:
                claims.append({"path": relative, "line": number, "text": clip(bullet.group(1), 200)})
    return claims


# --------------------------------------------------------------------------- routes


INTERCEPT_RE = re.compile(r"^(?:\(\.{1,3}\))+")


def clean_segments(segments: list[str], drop_slots: bool = False) -> list[str]:
    """Drop route groups (and Next parallel slots); keep dynamic segments visible."""
    cleaned = []
    for segment in segments:
        if drop_slots:
            segment = INTERCEPT_RE.sub("", segment)  # (.)photo presents /photo
            if segment.startswith("@") and "[" not in segment:
                continue
        if not segment or (segment.startswith("(") and segment.endswith(")")):
            continue
        cleaned.append(segment)
    return cleaned


def flat_route(parts: list[str]) -> str | None:
    """Route for flat-file conventions (Remix, React Router 7, TanStack Router).

    Returns None for layouts, root files, and ignored files, which are not destinations.
    """
    segments: list[str] = []
    for part in parts:
        segments.extend(part.split("."))
    if not segments:
        return None
    last = segments[-1]
    if last.startswith(("__", "-")) or (last.startswith("_") and last != "_index") or last == "lazy" and len(segments) == 1:
        return None
    cleaned = []
    for segment in segments:
        if segment in {"route", "lazy", "index", "_index", "page", ""}:
            continue
        if segment.startswith(("__", "-")):
            return None
        if segment.startswith("_") or (segment.startswith("(") and segment.endswith(")")):
            continue
        if segment.startswith("$"):
            segment = "[" + (segment[1:] or "splat") + "]"
        cleaned.append(segment.rstrip("_"))
    return "/" + "/".join(cleaned)


def routing_dir(parts: list[str], name: str, package_roots: set[str]) -> int | None:
    """Index of a routing directory that sits at a package root or directly under its src/."""
    for index, part in enumerate(parts[:-1]):
        if part != name:
            continue
        parent = "/".join(parts[:index])
        if parent in package_roots:
            return index
        if index >= 1 and parts[index - 1] == "src" and "/".join(parts[:index - 1]) in package_roots:
            return index
    return None


def file_route(relative: str, stack: set[str], package_roots: set[str]) -> tuple[str, str, str] | None:
    """Return (surface, kind, route) when a path follows a file-routing convention."""
    parts = relative.split("/")
    name = parts[-1]
    stem, _, ext = name.rpartition(".")
    ext = "." + ext

    if name.startswith("+") and "routes" in parts[:-1]:
        index = parts.index("routes")
        route = "/" + "/".join(clean_segments(parts[index + 1:-1]))
        if re.fullmatch(r"\+page\.(svelte|md|svx)", name):
            return "screens", "sveltekit", route
        if re.fullmatch(r"\+server\.(ts|js)", name):
            return "endpoints", "sveltekit", route
        return None

    if len(parts) >= 4 and parts[-4:-2] == ["supabase", "functions"] and stem == "index":
        return "endpoints", "edge-function", "/" + parts[-2]

    if ext in JS_SUFFIXES | {".mdx"}:
        index = routing_dir(parts, "app", package_roots)
        if index is not None:
            inner = parts[index + 1:-1]
            if inner[:1] == ["routes"] and stack & {"remix", "tanstack-router"}:
                route = flat_route(inner[1:] + [stem])
                return ("screens", "file-routes", route) if route is not None else None
            if "next" in stack or stem in {"page", "route"}:
                if stem == "page":
                    return "screens", "next-app", "/" + "/".join(clean_segments(inner, drop_slots=True))
                if stem == "route" and ext != ".mdx":
                    return "endpoints", "next-app", "/" + "/".join(clean_segments(inner, drop_slots=True))
            if "expo-router" in stack and "next" not in stack:
                if name.startswith(("_", "+")) or any(part in SCREEN_DIR_STOP for part in inner):
                    return None
                tail = [] if stem == "index" else [stem]
                return "screens", "expo-router", "/" + "/".join(clean_segments(inner + tail))

    index = routing_dir(parts, "pages", package_roots)
    if index is not None:
        inner = parts[index + 1:-1]
        tail = [] if stem == "index" else [stem]
        if "next" in stack and ext in JS_SUFFIXES | {".mdx"}:
            if inner[:1] == ["api"]:
                return "endpoints", "next-pages", "/" + "/".join(["api"] + inner[1:] + tail)
            if stem.startswith("_") or any(part in SCREEN_DIR_STOP for part in inner):
                return None
            return "screens", "next-pages", "/" + "/".join(inner + tail)
        if "nuxt" in stack and ext == ".vue":
            return "screens", "nuxt", "/" + "/".join(inner + tail)
        if "astro" in stack:
            if ext in {".astro", ".md", ".mdx"}:
                return "screens", "astro", "/" + "/".join(inner + tail)
            if ext in {".ts", ".js"}:
                return "endpoints", "astro", "/" + "/".join(inner + tail)

    if "tanstack-router" in stack and ext in {".tsx", ".jsx"}:
        index = routing_dir(parts, "routes", package_roots)
        if index is not None:
            route = flat_route(parts[index + 1:-1] + [stem])
            return ("screens", "file-routes", route) if route is not None else None

    if "nuxt" in stack and ext in {".ts", ".js"}:
        index = routing_dir(parts, "server", package_roots)
        if index is not None and parts[index + 1:index + 2] == ["api"]:
            cleaned = re.sub(r"\.(get|post|put|patch|delete)$", "", stem)
            tail = [] if cleaned == "index" else [cleaned]
            return "endpoints", "nuxt", "/" + "/".join(parts[index + 1:-1] + tail)
    return None


def generic_screen(relative: str, stack: set[str], siblings: dict[str, set[str]]) -> str | None:
    """Name a screen when a file sits in a screens-like directory or is named like one."""
    parts = relative.split("/")
    name = parts[-1]
    stem, _, ext = name.rpartition(".")
    ext = "." + ext
    if NATIVE_SCREEN_RE.match(name):
        return stem
    if ext not in {".tsx", ".jsx", ".vue", ".svelte", ".dart", ".swift", ".kt"}:
        return None
    if stem.startswith(("_", "+", ".")) or stem.lower() in NOT_A_SCREEN_STEMS:
        return None
    lowered = [part.lower() for part in parts[:-1]]
    for index, part in enumerate(lowered):
        if part not in SCREEN_DIR_NAMES:
            continue
        if FILE_ROUTER_OWNS.get(part, set()) & stack:
            return None  # the framework's own routing files are handled by file_route
        inner = lowered[index + 1:]
        if len(inner) > 2 or any(segment in SCREEN_DIR_STOP for segment in inner):
            return None
        if not inner:
            return stem
        folder = parts[-2]
        own = {s.lower() for s in siblings.get("/".join(parts[:-1]), set())}
        anchors = {"index", "page", folder.lower(), folder.lower() + "page", folder.lower() + "screen", folder.lower() + "view"}
        if own & anchors:
            # One screen per folder: only the anchor file is the destination.
            if stem.lower() not in anchors:
                return None
            return folder if stem.lower() in {"index", "page"} else stem
        return stem
    if SCREEN_NAME_RE.match(name):
        return stem
    return None


# --------------------------------------------------------------------------- scan


def count_controls(text: str, suffix: str) -> dict[str, int]:
    rules = NATIVE_CONTROLS if suffix in NATIVE_UI_SUFFIXES else MARKUP_CONTROLS
    return {label: len(pattern.findall(text)) for label, pattern in rules.items()}


PY_IMPORT_RE = re.compile(r"^\s*(?:from|import)\s+([A-Za-z_][\w]*)", re.MULTILINE)


def imported_packages(text: str, suffix: str) -> set[str]:
    """Package names a source file imports, normalized like dependency names."""
    if suffix == ".py":
        return {normalize_dep(name) for name in PY_IMPORT_RE.findall(text)}
    names = set()
    for specifier in IMPORT_RE.findall(text):
        if specifier.startswith((".", "/", "~", "#")):
            continue
        parts = specifier.split("/")
        names.add("/".join(parts[:2]) if specifier.startswith("@") and len(parts) > 1 else parts[0])
    return names


def import_stems(text: str) -> set[str]:
    stems = set()
    for match in IMPORT_RE.finditer(text):
        segments = [s for s in re.split(r"[/\\:]", match.group(1)) if s and s not in {".", ".."}]
        if not segments:
            continue
        stem = re.sub(r"\.(tsx?|jsx?|vue|svelte|mjs|cjs|dart)$", "", segments[-1])
        if stem == "index" and len(segments) > 1:
            stem = segments[-2]
        stems.add(stem)
    return stems


def is_static_route(route: str | None) -> bool:
    return bool(route) and route != "/" and not re.search(r"[\[\]:$*{}]", route)


def scan(root: Path, window_days: int) -> dict:
    relatives, truncated = walk(root)
    contents: dict[str, str] = {}
    budget = MAX_TOTAL_BYTES
    for relative in relatives:
        path = root / relative
        if not is_text_candidate(path):
            continue
        text = read_text(path)
        if text is None:
            continue
        budget -= len(text)
        if budget < 0:
            truncated = True
            break
        contents[relative] = text

    history = git_history(root, window_days)
    manifests = load_manifests(contents)
    stack_list = detect_stack(manifests, relatives)
    stack = set(stack_list)
    integrations = detect_integrations(manifests)
    packages = detect_packages(contents, manifests)
    skill_roots = frozenset(
        relative.rsplit("/", 1)[0] for relative in relatives
        if relative.endswith("/SKILL.md")
    )
    package_roots = {""} | {m["path"].rsplit("/", 1)[0] for m in manifests if "/" in m["path"]}
    siblings: dict[str, set[str]] = {}
    for relative in relatives:
        directory, _, name = relative.rpartition("/")
        siblings.setdefault(directory, set()).add(name.rpartition(".")[0] or name)

    screens: list[dict] = []
    endpoints: list[dict] = []
    commands: list[dict] = []
    models: dict[str, dict] = {}
    cli_options: set[str] = set()
    env_names: dict[str, str] = {}
    preference_keys: set[str] = set()
    unfinished: list[dict] = []
    todo_counts: dict[str, int] = {}
    link_hubs: list[dict] = []
    control_table: dict[str, dict] = {}
    literal_files: dict[str, Counter] = {}
    word_files: dict[str, Counter] = {}
    imports: dict[str, set[str]] = {}
    declared_routes: list[dict] = []
    nav_declared: list[dict] = []
    native_text: dict[str, str] = {}
    importers: Counter[str] = Counter()
    source_files = source_lines = ui_files = 0
    dir_all: Counter[str] = Counter()
    dir_files: Counter[str] = Counter()
    dir_lines: Counter[str] = Counter()
    for relative in relatives:
        segments = relative.split("/")[:-1]
        if any(segment.startswith(".") for segment in segments):
            continue
        for depth in range(1, min(len(segments), 4) + 1):
            dir_all["/".join(segments[:depth])] += 1

    def add_model(match: re.Match, kind: str, relative: str) -> None:
        name = match.group(1)
        if BOOKKEEPING_TABLE_RE.search(name):
            return
        models.setdefault(
            (name.lower(), kind in ORM_KINDS),
            {"name": name, "kind": kind, "path": relative, "line": line_of(match.string, match.start(1))},
        )

    for relative, text in contents.items():
        parts = relative.split("/")
        name = parts[-1]
        suffix = "." + name.rpartition(".")[2].lower() if "." in name else ""
        non_product = is_non_product(relative, skill_roots)
        is_source = suffix in SOURCE_SUFFIXES
        hidden = any(part.startswith(".") for part in parts[:-1])
        if is_source and not hidden:
            lines = sum(1 for line in text.splitlines() if line.strip())
            if not non_product:
                source_files += 1
                source_lines += lines
            for depth in range(1, min(len(parts) - 1, 4) + 1):
                directory = "/".join(parts[:depth])
                dir_files[directory] += 1
                dir_lines[directory] += lines
        if non_product or hidden:
            continue
        stem = name.rpartition(".")[0]

        if suffix in SOURCE_SUFFIXES | MARKUP_SUFFIXES:
            for literal, count in Counter(PATH_LITERAL_RE.findall(text)).items():
                literal_files.setdefault(literal, Counter())[relative] = count
            for word, count in Counter(WORD_LITERAL_RE.findall(text)).items():
                word_files.setdefault(word, Counter())[relative] = count
            stems = import_stems(text)
            if stems:
                imports[relative] = stems
            if suffix == ".py" or suffix in JS_SUFFIXES | {".vue", ".svelte", ".astro"}:
                importers.update(imported_packages(text, suffix))
            if suffix in NATIVE_UI_SUFFIXES | {".java"}:
                native_text[relative] = text
            if UNFINISHED_RE.search(text) or TODO_RE.search(text):
                todos = 0
                for number, line in enumerate(text.splitlines(), start=1):
                    phrases = {m.group(0).lower() for m in UNFINISHED_RE.finditer(line)}
                    notes = {m.group(0) for m in TODO_RE.finditer(line)}
                    if len(phrases) > 1 or len(notes) > 1:
                        continue  # a line naming several markers defines them; it is not one
                    if phrases and len(unfinished) < 400:
                        unfinished.append({"path": relative, "line": number, "text": clip(line, 160)})
                    todos += len(notes)
                if todos:
                    todo_counts[relative] = todos

        if suffix in UI_SUFFIXES or suffix in JS_SUFFIXES:
            controls = count_controls(text, suffix)
            total_controls = sum(controls.values())
            if suffix in UI_SUFFIXES:
                ui_files += 1
            if total_controls:
                control_table[relative] = {**controls, "total": total_controls}
            if suffix != ".html" and not GENERATED_FILE_RE.search(relative):
                found = LINK_TARGET_RE.findall(text)
                if not ROUTER_MARKER_RE.search(text):
                    found += PATH_KEY_TARGET_RE.findall(text)  # a nav table, not a route table
                targets = {t.rstrip("/") or "/" for t in found if not NOT_A_DESTINATION_RE.search(t)}
                destinations = len(targets) + len(NAV_ITEM_RE.findall(text))
                named = bool(NAV_NAME_RE.search(stem) or (stem == "index" and len(parts) > 1 and NAV_NAME_RE.search(parts[-2])))
                if destinations >= 4 or (named and destinations >= 2):
                    link_hubs.append({"path": relative, "destinations": destinations, "named_like_navigation": named})

        # Screens and endpoints from routing conventions --------------------------------
        routed = file_route(relative, stack, package_roots)
        if routed:
            surface, kind, route = routed
            if surface == "screens":
                screens.append({"route": route or "/", "path": relative, "kind": kind})
            else:
                exports = {m.group(1): line_of(text, m.start()) for m in HTTP_EXPORT_RE.finditer(text)}
                for method in sorted(exports) or ["ANY"]:
                    entry = {"method": method, "route": route or "/", "path": relative, "kind": kind}
                    if method in exports:
                        entry["line"] = exports[method]
                    endpoints.append(entry)
        else:
            screen_name = generic_screen(relative, stack, siblings)
            if screen_name:
                screens.append({"route": None, "name": screen_name, "path": relative, "kind": "screen-file"})

        # Routes declared in code --------------------------------------------------------
        if suffix in JS_SUFFIXES | {".vue", ".svelte"}:
            for match in JSX_ROUTE_RE.finditer(text):
                route = match.group("a") or match.group("b") or match.group("c") or ""
                component = JSX_COMPONENT_RE.search(match.group("attrs") + " " + match.group("rest"))
                declared_routes.append({
                    "route": route, "path": relative, "component": component.group(1) if component else None,
                })
            if ROUTER_MARKER_RE.search(text):
                for match in OBJECT_ROUTE_RE.finditer(text):
                    component = OBJECT_COMPONENT_RE.search(match.group("rest"))
                    target = next((g for g in component.groups() if g), None) if component else None
                    declared_routes.append({"route": match.group(1), "path": relative, "component": target})
            for match in NAV_SCREEN_RE.finditer(text):
                component = NAV_COMPONENT_RE.search(match.group("attrs") + " " + match.group("rest"))
                nav_declared.append({
                    "name": match.group(2) or match.group(3), "path": relative,
                    "component": component.group(1) if component else None,
                })

        # Server endpoints -----------------------------------------------------------------
        if suffix in JS_SUFFIXES:
            for match in EXPRESS_RE.finditer(text):
                endpoints.append({
                    "method": match.group("verb").upper().replace("ALL", "ANY"),
                    "route": match.group("route"), "path": relative, "kind": "http-handler",
                    "line": line_of(text, match.start()),
                })
            controller = NEST_CONTROLLER_RE.search(text)
            if controller:
                prefix = "/" + (controller.group(1) or "").strip("/")
                for match in NEST_METHOD_RE.finditer(text):
                    tail = (match.group(2) or "").strip("/")
                    route = (prefix.rstrip("/") + "/" + tail).rstrip("/") or "/"
                    endpoints.append({"method": match.group(1).upper(), "route": route, "path": relative, "kind": "nest", "line": line_of(text, match.start())})
            if TRPC_MARKER_RE.search(text):
                for match in TRPC_PROC_RE.finditer(text):
                    endpoints.append({"method": "RPC", "route": match.group(1), "path": relative, "kind": "trpc", "line": line_of(text, match.start())})
            if USE_SERVER_RE.match(text):
                for match in SERVER_ACTION_RE.finditer(text):
                    endpoints.append({
                        "method": "ACTION", "route": match.group(1) or match.group(2), "path": relative,
                        "kind": "server-action", "line": line_of(text, match.start()),
                    })
            if "convex" in parts[:-1] and "_generated" not in parts:
                for match in CONVEX_RE.finditer(text):
                    endpoints.append({"method": match.group(2).upper(), "route": match.group(1), "path": relative, "kind": "convex", "line": line_of(text, match.start())})
            for match in CLOUD_FN_RE.finditer(text):
                endpoints.append({"method": match.group(2), "route": match.group(1), "path": relative, "kind": "cloud-function", "line": line_of(text, match.start())})
        elif suffix == ".py":
            prefixes = {}
            for match in PY_PREFIX_RE.finditer(text):
                prefix = PY_PREFIX_ARG_RE.search(match.group("args"))
                if prefix:
                    prefixes[match.group(1)] = prefix.group(1).rstrip("/")
            for match in PY_DECORATOR_RE.finditer(text):
                receiver = match.group("recv")
                if receiver.split(".")[0] in {"pytest", "mock", "patch", "click", "typer"}:
                    continue
                verb = match.group("verb")
                methods = [verb.upper()]
                if verb == "route":
                    listed = PY_METHODS_RE.search(match.group("rest"))
                    methods = re.findall(r"[A-Z]+", listed.group(1).upper()) if listed else ["GET"]
                route = prefixes.get(receiver, "") + match.group("route") or "/"
                for method in methods:
                    endpoints.append({
                        "method": method, "route": route, "path": relative, "kind": "http-handler",
                        "line": line_of(text, match.start()) + (1 if text[match.start()] == "\n" else 0),
                    })
            if name == "urls.py":
                for match in DJANGO_PATH_RE.finditer(text):
                    endpoints.append({"method": "ANY", "route": "/" + match.group(1), "path": relative, "kind": "django-url", "line": line_of(text, match.start())})
        elif suffix == ".rb" and relative.endswith("config/routes.rb"):
            for match in RAILS_ROUTE_RE.finditer(text):
                endpoints.append({"method": match.group(1).upper(), "route": match.group(2), "path": relative, "kind": "rails-route", "line": line_of(text, match.start())})
        elif suffix == ".go":
            for match in GO_ROUTE_RE.finditer(text):
                verb = match.group(1).upper()
                endpoints.append({
                    "method": "ANY" if verb.startswith("HANDLE") else verb, "route": match.group(2),
                    "path": relative, "kind": "http-handler", "line": line_of(text, match.start()),
                })
            if "cobra.Command" in text:
                for match in COBRA_RE.finditer(text):
                    commands.append({"name": match.group(1), "path": relative, "kind": "cobra", "line": line_of(text, match.start())})
        elif suffix in {".graphql", ".gql"}:
            for root_type in GRAPHQL_ROOT_RE.finditer(text):
                for field in GRAPHQL_FIELD_RE.finditer(root_type.group(2)):
                    endpoints.append({
                        "method": root_type.group(1).upper(), "route": field.group(1), "path": relative,
                        "kind": "graphql", "line": line_of(text, root_type.start(2) + field.start(1)),
                    })

        # Commands ---------------------------------------------------------------------------
        inside_skill = any(relative.startswith(skill_root + "/") for skill_root in skill_roots)
        if inside_skill:
            pass  # run by the agent, never typed by a user
        elif suffix == ".py":
            for match in ARGPARSE_RE.finditer(text):
                commands.append({"name": match.group(1), "path": relative, "kind": "argparse", "line": line_of(text, match.start())})
            for match in CLICK_RE.finditer(text):
                if match.group("recv") in {"click", "typer"}:
                    continue  # the root command or group is the program itself
                named = CLICK_NAME_RE.search(match.group("args") or "")
                command = named.group(1) if named else None
                if command is None:
                    following = PY_DEF_RE.search(text, match.end())
                    command = following.group(1).replace("_", "-") if following else None
                if command:
                    commands.append({
                        "name": command, "path": relative, "kind": "click-" + match.group("kind"),
                        "line": line_of(text, match.start("recv")),
                    })
        elif suffix in JS_SUFFIXES and ".command(" in text and re.search(r"\b(commander|yargs|cac|program)\b", text):
            for match in JS_COMMAND_RE.finditer(text):
                commands.append({"name": match.group(1), "path": relative, "kind": "js-cli", "line": line_of(text, match.start())})
        elif suffix == ".rs":
            for enum in CLAP_ENUM_RE.finditer(text):
                depth, index = 1, enum.end()
                while index < len(text) and depth:
                    depth += {"{": 1, "}": -1}.get(text[index], 0)
                    index += 1
                body = re.sub(r"\{[^{}]*\}|\([^()]*\)", "", text[enum.end():index - 1])
                for variant in CLAP_VARIANT_RE.finditer(body):
                    commands.append({
                        "name": variant.group(1), "path": relative, "kind": "clap",
                        "line": line_of(text, enum.start()),
                    })
        if not inside_skill and (suffix == ".py" or suffix in JS_SUFFIXES):
            cli_options.update(CLI_OPTION_RE.findall(text))

        # Data models --------------------------------------------------------------------------
        if suffix == ".prisma":
            for match in PRISMA_MODEL_RE.finditer(text):
                add_model(match, "prisma", relative)
        elif suffix == ".py":
            for pattern, kind in ((DJANGO_MODEL_RE, "django"), (TABLENAME_RE, "sqlalchemy"), (SQLMODEL_RE, "sqlmodel")):
                for match in pattern.finditer(text):
                    add_model(match, kind, relative)
        elif suffix == ".sql":
            for match in SQL_TABLE_RE.finditer(text):
                add_model(match, "sql", relative)
        elif suffix == ".rb":
            if relative.endswith("db/schema.rb") or "/migrate/" in relative:
                for match in RAILS_TABLE_RE.finditer(text):
                    add_model(match, "rails", relative)
        elif suffix == ".swift":
            for match in SWIFTDATA_RE.finditer(text):
                add_model(match, "swiftdata", relative)
        if suffix in JS_SUFFIXES | {".kt", ".java"}:
            for pattern, kind in (
                (DRIZZLE_RE, "drizzle"), (ENTITY_RE, "entity"), (MONGOOSE_RE, "mongoose"),
                (SEQUELIZE_RE, "sequelize"), (CONVEX_TABLE_RE, "convex"),
            ):
                for match in pattern.finditer(text):
                    add_model(match, kind, relative)
            if "firestore" in text.lower():
                for match in FIRESTORE_RE.finditer(text):
                    add_model(match, "firestore", relative)

        # Settings ---------------------------------------------------------------------------
        if is_source:
            for match in ENV_ACCESS_RE.finditer(text):
                env_names.setdefault(next(group for group in match.groups() if group), relative)
            for pattern in PREFERENCE_KEY_RES:
                for match in pattern.finditer(text):
                    if not NOT_A_PREFERENCE_RE.search(match.group(1)):
                        preference_keys.add(match.group(1))

    # Raw SQL tables are usually the migrations behind an ORM schema; count them once.
    has_orm = any(model["kind"] in ORM_KINDS for model in models.values())
    folded_sql = sum(1 for model in models.values() if model["kind"] == "sql") if has_orm else 0
    model_list = sorted(
        (model for model in models.values() if not (has_orm and model["kind"] == "sql")),
        key=lambda model: (model["name"].lower(), model["path"]),
    )

    # Merge declared routes with screen files -----------------------------------------------
    by_stem: dict[str, dict] = {}
    for screen in screens:
        if screen["kind"] == "screen-file":
            by_stem.setdefault(screen["name"], screen)
            by_stem.setdefault(screen["path"].rsplit("/", 1)[-1].rpartition(".")[0], screen)
    per_file = Counter(declared["path"] for declared in declared_routes)
    declared_routes.sort(key=lambda declared: (-per_file[declared["path"]], declared["path"]))
    seen_routes: set[str] = {screen["route"] for screen in screens if screen.get("route")}
    for declared in declared_routes:
        raw = declared["route"]
        if "*" in raw:
            continue
        route = raw if raw.startswith("/") else "/" + raw
        relative_route = not raw.startswith("/")
        target = by_stem.get(declared["component"]) if declared["component"] else None
        if target is not None:
            if target.get("route") is None:
                target["route"] = route
                target["declared_in"] = declared["path"]
                target["relative_route"] = relative_route
                seen_routes.add(route)
            continue
        if route in seen_routes:
            continue
        seen_routes.add(route)
        screens.append({
            "route": route, "path": declared["path"], "kind": "declared-route",
            "declared_in": declared["path"], "relative_route": relative_route,
            **({"component": declared["component"]} if declared["component"] else {}),
        })
    seen_names: set[str] = set()
    for declared in nav_declared:
        target = by_stem.get(declared["component"]) if declared["component"] else None
        if target is not None:
            target.setdefault("screen_name", declared["name"])
            target.setdefault("declared_in", declared["path"])
            continue
        if declared["name"] in seen_names:
            continue
        seen_names.add(declared["name"])
        screens.append({
            "route": None, "name": declared["name"], "screen_name": declared["name"],
            "path": declared["path"], "kind": "navigator-screen", "declared_in": declared["path"],
        })

    # How many other files lead to each screen ---------------------------------------------------
    literal_keys = sorted(literal_files)

    def files_naming(route: str, own: str, declared_in: str | None) -> int:
        hits: Counter[str] = Counter()
        for literal in literal_keys:
            if literal == route or literal.rstrip("/") == route or literal.startswith(route + "/"):
                hits.update(literal_files[literal])
        if declared_in:
            hits[declared_in] -= 1  # the declaration itself is not a link
        return sum(1 for other, count in hits.items() if count > 0 and other != own)

    static_routes = {screen["route"] for screen in screens if is_static_route(screen.get("route"))}

    def files_building(route: str, own: str) -> int | None:
        """Files that build a link into a dynamic route: its static prefix followed by a value."""
        prefix = re.split(r"[\[:$*{]", route, maxsplit=1)[0]
        if prefix.count("/") < 2 or not prefix.endswith("/"):
            return None  # no static prefix to look for
        hits: set[str] = set()
        for literal in literal_keys:
            if literal == route:
                hits.update(literal_files[literal])
            elif literal.startswith(prefix) and literal.rstrip("/") not in static_routes and not any(
                literal.startswith(known + "/") for known in static_routes if known.startswith(prefix)
            ):
                hits.update(literal_files[literal])
        hits.discard(own)
        return len(hits)

    for screen in screens:
        own = screen["path"]
        declared_in = screen.get("declared_in")
        route = screen.get("route")
        measured = False
        linked = 0
        if is_static_route(route) and not screen.get("relative_route"):
            linked += files_naming(route, own if screen["kind"] != "declared-route" else "", declared_in)
            measured = True
        elif route and route != "/" and not screen.get("relative_route") and screen["kind"] != "declared-route":
            built = files_building(route, own)
            if built is not None:
                linked += built
                measured = True
        if screen.get("screen_name"):
            hits = Counter(word_files.get(screen["screen_name"], {}))
            if declared_in:
                hits[declared_in] -= 1
            linked += sum(1 for other, count in hits.items() if count > 0 and other != own)
            measured = True
        if screen["kind"] == "screen-file" and not route and not screen.get("screen_name"):
            stem = own.rsplit("/", 1)[-1].rpartition(".")[0]
            if stem in ENTRY_SCREEN_STEMS:
                measured = False
            elif own in native_text:
                linked = sum(1 for other, text in native_text.items() if other != own and re.search(rf"\b{re.escape(stem)}\b", text))
                measured = True
            else:
                stem = own.split("/")[-2] if stem in {"index", "page"} and "/" in own else stem
                linked = sum(1 for other, stems in imports.items() if other != own and stem in stems)
                measured = True
        screen["linked_from"] = linked if measured else None
        screen.pop("relative_route", None)
        controls = control_table.get(own)
        if controls and screen["kind"] not in {"declared-route", "navigator-screen"}:
            screen["controls"] = controls["total"]
        stamp(screen, history)

    # Dynamic routes are often linked from data, so they stay out of this list; their own
    # linked_from still shows whether any file builds a link to them.
    unlinked = [
        {"route": s.get("route"), "name": s.get("name") or s.get("screen_name"), "path": s["path"]}
        for s in screens
        if s["linked_from"] == 0 and not SPECIAL_ROUTE_RE.search(s.get("route") or "")
        and (not s.get("route") or is_static_route(s["route"]))
    ]

    # Dedupe and stamp ---------------------------------------------------------------------------
    unique_endpoints: dict[tuple, dict] = {}
    for endpoint in endpoints:
        unique_endpoints.setdefault((endpoint["method"], endpoint["route"], endpoint["path"]), endpoint)
    endpoints = [stamp(e, history) for e in unique_endpoints.values()]
    unique_commands: dict[tuple, dict] = {}
    for command in commands:
        unique_commands.setdefault((command["name"], command["path"]), command)
    for manifest in manifests:
        if is_non_product(manifest["path"]):
            continue
        for binary in manifest["bins"]:
            unique_commands.setdefault((binary, manifest["path"]), {"name": binary, "path": manifest["path"], "kind": "executable"})
    commands = [stamp(c, history) for c in unique_commands.values()]
    model_list = [stamp(m, history) for m in model_list]
    packages = [stamp(package, history) for package in packages]
    date_shared_items(root, history, [endpoints, commands, model_list])
    screens.sort(key=lambda s: ((s.get("route") or "~"), s["path"]))
    endpoints.sort(key=lambda e: (e["route"], e["method"], e["path"]))
    commands.sort(key=lambda c: (c["name"], c["path"]))

    flag_like = sorted(name for name in env_names if FLAG_NAME_RE.match(name))
    settings_screens = sorted(
        (
            {"path": path, "settings": counts["toggles"] + counts["choices"] + counts["inputs"], **counts}
            for path, counts in control_table.items()
            if SETTINGS_PATH_RE.search(path.rsplit("/", 1)[-1]) or ("/" in path and SETTINGS_PATH_RE.search(path.split("/")[-2]))
        ),
        key=lambda item: (-item["total"], item["path"]),
    )
    dense = sorted(
        ({"path": path, **counts} for path, counts in control_table.items()),
        key=lambda item: (-item["total"], item["path"]),
    )[:15]
    link_hubs.sort(key=lambda item: (-item["destinations"], item["path"]))
    surface_paths = {s["path"] for s in screens} | {e["path"] for e in endpoints} | {c["path"] for c in commands}
    todo_in_surface = sorted(
        ({"path": path, "count": count} for path, count in todo_counts.items() if path in surface_paths),
        key=lambda item: (-item["count"], item["path"]),
    )

    # Growth and areas -----------------------------------------------------------------------------
    growth: dict = {"available": history.get("available", False)}
    area_added: dict[str, str] = {}
    if history.get("available"):
        quarters: dict[str, Counter] = {}
        for label, items in (
            ("screens", screens), ("endpoints", endpoints), ("commands", commands),
            ("data_models", model_list), ("packages", packages),
        ):
            for item in items:
                if item.get("added"):
                    quarters.setdefault(quarter_of(item["added"]), Counter())[label] += 1
        growth["by_quarter"] = [
            {
                "quarter": quarter,
                "commits": history["commits_by_quarter"].get(quarter, 0),
                **{
                    label: quarters.get(quarter, Counter()).get(label, 0)
                    for label in ("screens", "endpoints", "commands", "data_models", "packages")
                },
            }
            for quarter in sorted(set(quarters) | set(history["commits_by_quarter"]))
        ]
        growth["shallow_history"] = history["shallow"]
        for path, date in history["_added"].items():
            segments = path.split("/")[:-1]
            for depth in range(1, min(len(segments), 4) + 1):
                directory = "/".join(segments[:depth])
                if directory in dir_all and date < area_added.get(directory, "9999"):
                    area_added[directory] = date
    areas = []
    for directory in dir_all:
        parent = directory.rpartition("/")[0]
        if parent and dir_all.get(parent) == dir_all[directory]:
            continue  # the parent holds nothing else; one row is enough
        row = {
            "path": directory, "files": dir_all[directory],
            "source_files": dir_files[directory], "source_lines": dir_lines[directory],
        }
        if is_non_product(directory + "/x", skill_roots):
            row["non_product"] = True
        if history.get("available"):
            row.update({
                "added": area_added.get(directory),
                "commits": history["_dir_commits"].get(directory, 0),
                "recent_commits": history["_dir_recent"].get(directory, 0),
            })
        areas.append(row)
    # Top-level directories lead, then the product's own areas, then tests and tooling.
    areas.sort(key=lambda row: (
        "/" in row["path"], row.get("non_product", False),
        -row.get("recent_commits", 0), -row.get("commits", 0), -row["source_lines"], -row["files"], row["path"],
    ))

    recognized = bool(screens or endpoints or commands or model_list or packages)
    if recognized:
        note = "Recognized routing, command, data, or package conventions. Treat the lists as a floor: read the entry points for surface the patterns miss."
    else:
        note = "No routing, command, data-model, or package convention was recognized. Inventory the surface by reading the entry points and documentation."
    for integration in integrations:
        # Python import names often differ from package names, so a miss there proves nothing.
        counts = [importers.get(normalize_dep(dependency) if not dependency.startswith("@") else dependency, 0)
                  for dependency in integration["dependencies"]]
        javascript = all(path.endswith("package.json") for path in integration["manifests"])
        integration["imported_by_files"] = sum(counts) if (javascript or sum(counts)) else None
    analytics = [i for i in integrations if i["kind"] == "analytics"]

    recent_log = history.get("_recent_log", [])
    for key in list(history):
        if key.startswith("_"):
            del history[key]

    models_block = cap(model_list)
    models_block["sql_tables_folded_into_orm_models"] = folded_sql
    return {
        "schema": SCAN_SCHEMA,
        "root": str(root),
        "file_count": len(relatives),
        "truncated": truncated,
        "history": history,
        "purpose_sources": purpose_sources(contents, manifests),
        "claimed_features": cap(claimed_features(contents), 80),
        "direction_documents": sorted(
            relative for relative in relatives
            if relative.count("/") <= 2 and relative.rsplit(".", 1)[-1].lower() in {"md", "markdown", "txt"}
            and DIRECTION_DOC_RE.search(relative.rsplit("/", 1)[-1].rsplit(".", 1)[0])
        )[:30],
        "release_notes": sorted(
            relative for relative in relatives
            if relative.count("/") <= 1 and RELEASE_NOTES_RE.match(relative.rsplit("/", 1)[-1])
        ),
        "stack": stack_list,
        "coverage": {
            "recognized": recognized,
            "ui_files": ui_files,
            "screens": len(screens),
            "endpoints": len(endpoints),
            "commands": len(commands),
            "data_models": len(model_list),
            "packages": len(packages),
            "note": note,
        },
        "surface": {
            "screens": cap(screens),
            "endpoints": cap(endpoints),
            "commands": cap(commands),
            "data_models": models_block,
            "packages": cap(packages),
            "integrations": integrations,
            "navigation": link_hubs[:12],
            "settings": {
                "flag_like_variables": cap(flag_like, 80),
                "preference_keys": cap(sorted(preference_keys), 80),
                "command_options": cap(sorted(cli_options), 120),
                "settings_screens": settings_screens[:15],
                "environment_variables": cap(
                    [{"name": name, "path": env_names[name]} for name in sorted(env_names)], 60
                ),
            },
        },
        "signals": {
            "unlinked_screens": cap(unlinked, 60),
            "unfinished_markers": cap(unfinished, 60),
            "todos_in_surface_files": cap(todo_in_surface, 40),
            "dense_ui_files": dense,
            "usage_evidence": {
                "analytics": sorted({d for a in analytics for d in a["dependencies"]}),
                "note": (
                    "An analytics dependency is installed; ask the owner for the numbers."
                    if analytics else
                    "No analytics dependency found; usage is whatever the owner can say or measure."
                ),
            },
        },
        "growth": growth,
        "recent_commits": cap(recent_log, 60),
        "areas": {
            "window_days": window_days,
            **cap(areas, 40),
        },
        "weight": {
            "source_files": source_files,
            "source_lines": source_lines,
            "manifests": [
                {"path": m["path"], "runtime_dependencies": len(m["runtime"]), "dev_dependencies": len(m["dev"])}
                for m in manifests
            ],
        },
    }


# --------------------------------------------------------------------------- report check

SECTION_RE = re.compile(r"^## (\d)\. (.+?)\s*$", re.MULTILINE)
ROW_RE = re.compile(r"^\|\s*([A-Z]\d+)\s*\|(.*)$")
MEASURE_ROW_RE = re.compile(r"^\|\s*([A-Za-z][A-Za-z \-]+?)\s*\|\s*([^|]*?)\s*\|\s*$")
ITEM_RE = re.compile(r"^- ([A-Z]\d+) (.+?)\s*$")
CITED_ITEM_RE = re.compile(r"^- ([A-Z]\d+) \(([A-Z]\d+(?:, ?[A-Z]\d+)*)\) (.+?)\s*$")
READING_RE = re.compile(r"^- \(([A-Z]\d+(?:, ?[A-Z]\d+)*)\) (supports|contradicts|mixed|silent)\b(.*)$")
GUIDE_COMMENT_RE = re.compile(r"<!--\s*guide:")
HISTORY_RE = re.compile(r"^- (\d{4}-\d{2}-\d{2}): (.+?)\s*$")
URL_RE = re.compile(r"https?://[^\s|)>\]]+")
CHECKED_RE = re.compile(r"checked (\d{4}-\d{2}-\d{2})")
PLACEHOLDER_RE = re.compile(r"<(?!https?://|!--|/)([A-Za-z][^<>|\n]* [^<>|\n]*)>")
USAGE_RE = re.compile(r"^(unknown|owner: (regular|rare|never)|measured: \S.*)$")
HTML_NAMES = {"a", "img", "span", "div", "details", "summary", "br", "p", "sub", "sup", "kbd", "code"}


def split_cells(rest: str) -> list[str]:
    return [cell.strip() for cell in re.split(r"(?<!\\)\|", rest.strip().rstrip("|"))]


def split_sections(text: str) -> dict[str, str]:
    sections: dict[str, str] = {}
    matches = list(SECTION_RE.finditer(text))
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        sections[match.group(2).strip()] = text[match.end():end]
    return sections


def subsections(body: str) -> dict[str, list[str]]:
    buckets: dict[str, list[str]] = {"": []}
    current = ""
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("### "):
            current = stripped[4:].strip().lower()
            buckets.setdefault(current, [])
            continue
        buckets[current].append(stripped)
    return buckets


def valid_date(value: str) -> bool:
    try:
        dt.date.fromisoformat(value)
    except ValueError:
        return False
    return True


def parse_report(text: str) -> tuple[dict, list[str]]:
    errors: list[str] = []
    if REPORT_MARKER not in text:
        errors.append(f"missing report marker {REPORT_MARKER}")
    found = [match.group(2).strip() for match in SECTION_RE.finditer(text)]
    sections = split_sections(text)
    for name in REPORT_SECTIONS:
        if name not in sections:
            errors.append(f"missing section: {name}")
    if errors:
        return {}, errors
    if [name for name in found if name in REPORT_SECTIONS] != REPORT_SECTIONS:
        errors.append("sections must appear once each, in order: " + ", ".join(REPORT_SECTIONS))
    for match in PLACEHOLDER_RE.finditer(text):
        if match.group(1).split()[0].lower() not in HTML_NAMES:
            errors.append(f"template placeholder left in report: <{clip(match.group(1), 60)}>")
    if GUIDE_COMMENT_RE.search(text):
        errors.append("template guidance left in report: delete every '<!-- guide: ... -->' comment")

    # 1. Promise
    promise_lines = [line.strip() for line in sections["Promise"].splitlines() if line.strip()]
    promise = " ".join(line for line in promise_lines if not line.startswith(("Source:", "Stage:", "<!--")))
    if not promise:
        errors.append("Promise must state who the product is for and what it does, in one sentence")
    if not any(line.startswith("Source:") and len(line) > len("Source:") + 1 for line in promise_lines):
        errors.append("Promise needs a 'Source:' line naming where the sentence came from")

    # 3. Features
    features: dict[str, dict] = {}
    for line in sections["Features"].splitlines():
        match = ROW_RE.match(line.strip())
        if not match or not match.group(1).startswith("F"):
            continue
        feature_id = match.group(1)
        cells = split_cells(match.group(2))
        if len(cells) < 8:
            errors.append(f"{feature_id}: needs columns feature, class, evidence, cost, usage, verdict, decision, decided by")
            continue
        if feature_id in features:
            errors.append(f"duplicate feature id {feature_id}")
        title, klass, evidence, cost, usage, verdict, decision, decided_by = cells[:8]
        klass, cost, verdict, decision = klass.lower(), cost.lower(), verdict.lower(), decision.lower()
        decided_by = decided_by.lower()
        if not title:
            errors.append(f"{feature_id}: feature name is empty")
        if klass not in FEATURE_CLASSES:
            errors.append(f"{feature_id}: class {cells[1]!r} must be one of {FEATURE_CLASSES}")
        if cost not in FEATURE_COSTS:
            errors.append(f"{feature_id}: cost {cells[3]!r} must be one of {FEATURE_COSTS}")
        if not USAGE_RE.match(usage):
            errors.append(
                f"{feature_id}: usage {usage!r} must be 'unknown', 'owner: regular|rare|never', or 'measured: <numbers>'"
            )
        if verdict not in VERDICTS:
            errors.append(f"{feature_id}: verdict {cells[5]!r} must be one of {VERDICTS}")
        if decision not in VERDICTS + ["pending"]:
            errors.append(f"{feature_id}: decision {cells[6]!r} must be pending or one of {VERDICTS}")
        if not evidence or evidence in {"—", "-", "n/a"}:
            errors.append(f"{feature_id}: evidence column is empty")
        if klass == "core" and verdict in {"park", "cut"}:
            errors.append(f"{feature_id}: a core feature cannot be parked or cut; a failing core is a Direction finding")
        if verdict == "cut" and usage == "unknown":
            errors.append(f"{feature_id}: cut needs usage evidence; with usage unknown the verdict is park")
        pending = decision == "pending"
        if pending and decided_by not in {"—", "-", ""}:
            errors.append(f"{feature_id}: a pending decision has no decider; write — in Decided by")
        if not pending:
            if decided_by not in DECIDERS:
                errors.append(f"{feature_id}: decided by {cells[7]!r} must be one of {sorted(DECIDERS)}")
            elif decided_by == "audit" and not (decision == "keep" and verdict == "keep"):
                errors.append(f"{feature_id}: only the owner decides anything other than keeping a feature the audit would keep")
        features[feature_id] = {
            "id": feature_id, "class": klass, "cost": cost, "usage": usage, "verdict": verdict,
            "decision": decision, "decided_by": decided_by,
        }
    if not features:
        errors.append("Features must list at least one feature row (F1 ...)")

    # 2. Snapshot
    snapshot: dict[str, str] = {}
    for line in sections["Snapshot"].splitlines():
        match = MEASURE_ROW_RE.match(line.strip())
        if match and match.group(1) in SNAPSHOT_MEASURES:
            snapshot[match.group(1)] = match.group(2)
    for measure in SNAPSHOT_MEASURES:
        value = snapshot.get(measure)
        if value is None:
            errors.append(f"Snapshot is missing the measure {measure!r}")
        elif not re.fullmatch(r"\d+|n/a", value):
            errors.append(f"Snapshot {measure!r} must be a whole number or n/a, found {value!r}")
    if features and not errors_for_counts(snapshot):
        expected = {"Features": len(features)}
        for label, klass in (("Core", "core"), ("Supporting", "supporting"), ("Adjacent", "adjacent"), ("Off-promise", "off-promise")):
            expected[label] = sum(f["class"] == klass for f in features.values())
        for label, count in expected.items():
            if snapshot.get(label) != str(count):
                errors.append(f"Snapshot {label!r} says {snapshot.get(label)} but the Features table has {count}")

    # 4. Complexity
    findings: dict[str, dict] = {}
    for line in sections["Complexity"].splitlines():
        match = ROW_RE.match(line.strip())
        if not match or not match.group(1).startswith("X"):
            continue
        cells = split_cells(match.group(2))
        finding_id = match.group(1)
        if finding_id in findings:
            errors.append(f"duplicate complexity id {finding_id}")
        if len(cells) < 3 or not all(cells[:3]):
            errors.append(f"{finding_id}: needs a finding, its evidence, and the simpler shape")
        findings[finding_id] = {"id": finding_id}
    if len(findings) > 5:
        errors.append("Complexity is capped at five findings")
    if not findings and not re.search(r"^None\.\s*$", sections["Complexity"], re.MULTILINE):
        errors.append("Complexity with no findings must say 'None.'")

    # 5. Direction
    direction_parts = subsections(sections["Direction"])
    verdict_lines = [line for line in direction_parts[""] if line.lower().startswith("verdict:")]
    direction = None
    if len(verdict_lines) != 1:
        errors.append("Direction needs exactly one 'Verdict:' line")
    else:
        direction = verdict_lines[0].split(":", 1)[1].strip().lower()
        if direction not in DIRECTION_VERDICTS:
            errors.append(f"Direction verdict {direction!r} must be one of {DIRECTION_VERDICTS}")
    reason = [line for line in direction_parts[""] if line and not line.lower().startswith("verdict:")]
    if not reason:
        errors.append("Direction needs the reason for its verdict, with evidence")
    choices: dict[str, str] = {}
    for line in direction_parts.get("the choice", []):
        match = ITEM_RE.match(line)
        if match and match.group(1).startswith("D"):
            choices[match.group(1)] = match.group(2)
        elif line.startswith("- "):
            errors.append(f"malformed choice: {line!r}")
    if len(choices) > 3:
        errors.append("The choice is capped at three options")
    if direction in {"drifting", "split", "undefined"}:
        if len(choices) < 2:
            errors.append(f"A {direction} direction needs at least two options under 'The choice'")
        if sum("(recommended)" in body.lower() for body in choices.values()) != 1:
            errors.append("Exactly one option under 'The choice' must be marked (recommended)")

    # 6. Outside view
    outside_parts = subsections(sections["Outside view"])
    not_run = [line for line in outside_parts[""] if line.lower().startswith("not run:")]
    products: dict[str, dict] = {}
    for line in outside_parts[""]:
        match = ROW_RE.match(line)
        if not match or not match.group(1).startswith("O"):
            continue
        cells = split_cells(match.group(2))
        product_id = match.group(1)
        if product_id in products:
            errors.append(f"duplicate product id {product_id}")
        if len(cells) < 4 or not all(cells[:4]):
            errors.append(f"{product_id}: needs product, why comparable, what it covers, and source")
            continue
        source = cells[3]
        if source.lower() != "owner":
            if not URL_RE.search(source):
                errors.append(f"{product_id}: source must be a URL with 'checked YYYY-MM-DD', or 'owner'")
            checked = CHECKED_RE.search(source)
            if not checked or not valid_date(checked.group(1)):
                errors.append(f"{product_id}: source needs the date it was read, as 'checked YYYY-MM-DD'")
        products[product_id] = {"id": product_id}
    gaps: dict[str, str] = {}
    for line in outside_parts.get("gaps", []):
        match = ITEM_RE.match(line)
        if match and match.group(1).startswith("G"):
            gaps[match.group(1)] = match.group(2)
        elif line.startswith("- "):
            errors.append(f"malformed gap: {line!r}")
    readings = []
    for line in outside_parts.get("readings", []):
        match = READING_RE.match(line)
        if match:
            readings.extend(cited.strip() for cited in match.group(1).split(","))
        elif line.startswith("- "):
            errors.append(f"malformed reading: {line!r} (expected '- (F3) supports|contradicts|mixed: ...')")
    if not_run and (products or gaps or readings):
        errors.append("Outside view says 'Not run' but also lists products, readings, or gaps")
    if not_run and len(not_run[0]) <= len("Not run:") + 1:
        errors.append("'Not run:' needs its reason")
    if not not_run and not products:
        errors.append("Outside view needs comparable products with sources, or a 'Not run: <reason>' line")
    if len(products) > 5:
        errors.append("Outside view is capped at five products")
    if len(gaps) > 3:
        errors.append("Gaps are capped at three")

    known = set(features) | set(findings) | set(choices) | set(gaps) | set(products)
    for reading in readings:
        if reading not in known:
            errors.append(f"a reading cites unknown id {reading}")

    # 7. Next moves
    moves_parts = subsections(sections["Next moves"])
    for heading in moves_parts:
        if heading not in {"", "next", "then"}:
            errors.append(f"unknown heading under Next moves: {heading!r}")
    next_items, then_items = [], []
    for bucket, target in (("next", next_items), ("then", then_items)):
        for line in moves_parts.get(bucket, []):
            match = CITED_ITEM_RE.match(line)
            if match and match.group(1).startswith("N"):
                for cited in (part.strip() for part in match.group(2).split(",")):
                    if cited not in known:
                        errors.append(f"{match.group(1)} cites unknown id {cited}")
                target.append(match.group(1))
            elif line.startswith("- "):
                errors.append(f"malformed move: {line!r} (expected '- N1 (F3) what to do' or '- N1 (F3, X1) ...')")
    nothing = NOTHING_NEXT in sections["Next moves"].lower()
    if len(next_items) > 1:
        errors.append("Next holds exactly one move")
    if not next_items and not nothing:
        errors.append("Next needs one move citing an id, or the line 'Nothing obvious; next is whatever you decide to build.'")
    if len(then_items) > 4:
        errors.append("Then is capped at four moves")
    move_ids = next_items + then_items
    if len(move_ids) != len(set(move_ids)):
        errors.append("duplicate move ids")

    # 8. History
    history = []
    for line in sections["History"].splitlines():
        stripped = line.strip()
        match = HISTORY_RE.match(stripped)
        if match:
            if not valid_date(match.group(1)):
                errors.append(f"History has an invalid date: {match.group(1)}")
            history.append(match.group(1))
        elif stripped.startswith("- "):
            errors.append(f"malformed history line: {stripped!r} (expected '- YYYY-MM-DD: summary')")
    if not history:
        errors.append("History needs one dated line per audit")
    if history != sorted(history):
        errors.append("History lines must run oldest to newest")

    return {
        "features": features,
        "pending_decisions": [f["id"] for f in features.values() if f["decision"] == "pending"],
        "complexity_findings": len(findings),
        "direction": direction,
        "outside_view": "not run" if not_run else f"{len(products)} products",
        "gaps": len(gaps),
        "next": next_items,
        "then": then_items,
        "audits": len(history),
    }, errors


def errors_for_counts(snapshot: dict[str, str]) -> bool:
    """True when a class count is missing or not numeric, so the cross-check would only repeat it."""
    return any(not re.fullmatch(r"\d+", snapshot.get(label, "")) for label in ("Features", "Core", "Supporting", "Adjacent", "Off-promise"))


def check_report(path: Path) -> int:
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        fail(f"report not found: {path}")
    except OSError as exc:
        fail(f"cannot read report: {exc}")
    parsed, errors = parse_report(text)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    verdicts = Counter(feature["verdict"] for feature in parsed["features"].values())
    summary = {
        "ok": True,
        "features": len(parsed["features"]),
        "verdicts": {verdict: verdicts[verdict] for verdict in VERDICTS if verdicts[verdict]},
        "pending_decisions": parsed["pending_decisions"],
        "complexity_findings": parsed["complexity_findings"],
        "direction": parsed["direction"],
        "outside_view": parsed["outside_view"],
        "gaps": parsed["gaps"],
        "next": parsed["next"],
        "then": parsed["then"],
        "audits": parsed["audits"],
    }
    print(json.dumps(summary, indent=2))
    return 0


def atomic_write(path: Path, text: str) -> None:
    directory = path.parent
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    except BaseException:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise


# --------------------------------------------------------------------------- cli


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    scan_parser = sub.add_parser("scan", help="produce the read-only surface inventory")
    scan_parser.add_argument("--root", required=True)
    scan_parser.add_argument(
        "--out", help=f"write JSON here instead of stdout (inside the root it must be named {SCAN_NAME})"
    )
    scan_parser.add_argument(
        "--window-days", type=int, default=180,
        help="how far back 'recent' work reaches, counted from the newest commit (default 180)",
    )

    check_parser = sub.add_parser("check", help="validate a product audit report")
    check_parser.add_argument("--report", required=True)

    args = parser.parse_args(argv)
    if args.command == "scan":
        root = authorized_root(args.root)
        if args.window_days < 1:
            fail("--window-days must be positive")
        inventory = scan(root, args.window_days)
        payload = json.dumps(inventory, indent=2, sort_keys=True)
        if args.out:
            out = Path(os.path.abspath(os.path.expanduser(args.out)))
            try:
                inside = out.relative_to(root)
            except ValueError:
                inside = None
            if inside is not None and out.name != SCAN_NAME:
                fail(f"--out inside the project must be named {SCAN_NAME}")
            atomic_write(out, payload + "\n")
            print(json.dumps({"ok": True, "out": str(out), "coverage": inventory["coverage"]}))
        else:
            print(payload)
        return 0
    return check_report(Path(os.path.abspath(os.path.expanduser(args.report))))


if __name__ == "__main__":
    raise SystemExit(main())
