.PHONY: demo-gif badge-publish

demo-gif:
	@command -v vhs >/dev/null || { echo "vhs is required: https://github.com/charmbracelet/vhs"; exit 1; }
	vhs docs/assets/demo.tape

badge-publish:
	bash scripts/tt-publish-badge.sh
