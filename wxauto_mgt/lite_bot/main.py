from __future__ import annotations

import logging
import time

from wxauto_mgt.lite_bot.bot import WxAutoBot
from wxauto_mgt.lite_bot.config import load_config
from wxauto_mgt.lite_bot.wxauto_adapter import WxautoAdapter


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    config = load_config()
    bot = WxAutoBot(config)

    from wxauto import WeChat

    wx = WeChat()
    adapter = WxautoAdapter(wx)

    while True:
        for raw in adapter.poll_messages():
            message = adapter.parse_raw(raw)
            bot.handle_message(message, adapter)
        time.sleep(0.5)


if __name__ == "__main__":
    main()
