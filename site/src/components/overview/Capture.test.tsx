import { renderToStaticMarkup } from 'react-dom/server';
import { expect, test } from 'vitest';
import Capture from './Capture';

test('the server-rendered image stays readable while its expand action waits for hydration', () => {
	const html = renderToStaticMarkup(<Capture
		image={{ src: '/report.webp', srcSet: '/report.webp 800w', full: '/report.png', width: 800, height: 600 }}
		alt="Station report"
		caption="Five fictional stations."
	/>);
	expect(html).toMatch(/<button[^>]*disabled=""/);
	expect(html).toContain('src="/report.webp"');
	expect(html).toContain('alt="Station report"');
	expect(html).toContain('Five fictional stations.');
});
