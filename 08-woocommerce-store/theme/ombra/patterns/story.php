<?php
/**
 * Title: Story: made slowly
 * Slug: ombra/story
 * Categories: ombra, about
 * Keywords: about, story, media, text
 * Viewport width: 1400
 *
 * @package Ombra
 */

$ombra_points = array(
	array( __( 'Coconut-soy wax, cotton wicks', 'ombra' ), __( 'A soft, even burn with no black soot on the glass.', 'ombra' ) ),
	array( __( 'Poured by hand, 60 at a time', 'ombra' ), __( 'Each batch cures for two weeks before it ships, so the scent throw is full.', 'ombra' ) ),
	array( __( 'Vessels worth keeping', 'ombra' ), __( 'Amber glass, brushed tins and terracotta that go on to hold pens, plants or matches.', 'ombra' ) ),
);
?>
<!-- wp:group {"className":"ombra-section","style":{"spacing":{"padding":{"top":"var:preset|spacing|60","bottom":"var:preset|spacing|60"}}},"backgroundColor":"base-2","layout":{"type":"constrained"}} -->
<div class="wp-block-group ombra-section has-base-2-background-color has-background" style="padding-top:var(--wp--preset--spacing--60);padding-bottom:var(--wp--preset--spacing--60)">
<!-- wp:media-text {"align":"wide","mediaType":"image","mediaWidth":50,"verticalAlignment":"center","className":"ombra-story","style":{"spacing":{"blockGap":"0"}}} -->
<div class="wp-block-media-text alignwide is-stacked-on-mobile is-vertically-aligned-center ombra-story"><figure class="wp-block-media-text__media"><img src="<?php echo esc_url( ombra_image( 'story.jpg' ) ); ?>" alt="<?php esc_attr_e( 'Amber & Smoke candle burning next to a jar of long matches', 'ombra' ); ?>"/></figure><div class="wp-block-media-text__content">
<!-- wp:paragraph {"className":"ombra-eyebrow","textColor":"accent"} -->
<p class="ombra-eyebrow has-accent-color has-text-color"><?php esc_html_e( 'Our story', 'ombra' ); ?></p>
<!-- /wp:paragraph -->

<!-- wp:heading {"level":2} -->
<h2 class="wp-block-heading"><?php esc_html_e( 'Made slowly, for slow evenings', 'ombra' ); ?></h2>
<!-- /wp:heading -->

<!-- wp:paragraph -->
<p><?php esc_html_e( 'Ombra means shadow. We started with one candle and one question: what should a room feel like after the lights go down? Everything we make is an answer to that.', 'ombra' ); ?></p>
<!-- /wp:paragraph -->

<!-- wp:list {"className":"ombra-points is-style-no-bullets"} -->
<ul class="wp-block-list ombra-points is-style-no-bullets">
<?php foreach ( $ombra_points as $ombra_point ) : ?>
<!-- wp:list-item -->
<li><strong><?php echo esc_html( $ombra_point[0] ); ?></strong> <?php echo esc_html( $ombra_point[1] ); ?></li>
<!-- /wp:list-item -->
<?php endforeach; ?>
</ul>
<!-- /wp:list -->

<!-- wp:paragraph {"className":"ombra-link-arrow"} -->
<p class="ombra-link-arrow"><a href="<?php echo esc_url( ombra_page_url( 'our-story' ) ); ?>"><?php esc_html_e( 'Read our story', 'ombra' ); ?></a></p>
<!-- /wp:paragraph -->
</div></div>
<!-- /wp:media-text -->
</div>
<!-- /wp:group -->
