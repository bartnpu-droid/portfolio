<?php
/**
 * Title: Hero: lit candles
 * Slug: ombra/hero
 * Categories: ombra, banner
 * Keywords: hero, cover, banner
 * Viewport width: 1400
 *
 * @package Ombra
 */

?>
<!-- wp:cover {"url":"<?php echo esc_url( ombra_image( 'hero.jpg' ) ); ?>","alt":"","dimRatio":0,"customOverlayColor":"#17130f","isUserOverlayColor":true,"focalPoint":{"x":0.7,"y":0.55},"minHeight":86,"minHeightUnit":"vh","contentPosition":"center left","isDark":true,"align":"full","className":"ombra-hero","style":{"spacing":{"padding":{"top":"var:preset|spacing|60","bottom":"var:preset|spacing|60"},"margin":{"top":"0","bottom":"0"}}},"layout":{"type":"constrained","contentSize":"1320px"}} -->
<div class="wp-block-cover alignfull has-custom-content-position is-position-center-left ombra-hero" style="margin-top:0;margin-bottom:0;padding-top:var(--wp--preset--spacing--60);padding-bottom:var(--wp--preset--spacing--60);min-height:86vh"><img class="wp-block-cover__image-background" alt="" src="<?php echo esc_url( ombra_image( 'hero.jpg' ) ); ?>" style="object-position:70% 55%" data-object-fit="cover" data-object-position="70% 55%"/><span aria-hidden="true" class="wp-block-cover__background has-background-dim-0 has-background-dim" style="background-color:#17130f"></span><div class="wp-block-cover__inner-container">
<!-- wp:group {"className":"ombra-hero__text","style":{"spacing":{"blockGap":"1.4rem"}},"layout":{"type":"constrained","contentSize":"540px","justifyContent":"left"}} -->
<div class="wp-block-group ombra-hero__text">
<!-- wp:paragraph {"className":"ombra-eyebrow","textColor":"accent-2"} -->
<p class="ombra-eyebrow has-accent-2-color has-text-color"><?php esc_html_e( 'Hand-poured in small batches', 'ombra' ); ?></p>
<!-- /wp:paragraph -->

<!-- wp:heading {"level":1,"textColor":"base"} -->
<h1 class="wp-block-heading has-base-color has-text-color"><?php echo wp_kses( __( 'Light, and the shadow it&nbsp;makes', 'ombra' ), array() ); ?></h1>
<!-- /wp:heading -->

<!-- wp:paragraph {"textColor":"base-3","fontSize":"large"} -->
<p class="has-base-3-color has-text-color has-large-font-size"><?php esc_html_e( 'Coconut-soy candles and home fragrance in three scents: fig and cedar, sea salt and sage, amber and smoke. Made to burn clean and slow.', 'ombra' ); ?></p>
<!-- /wp:paragraph -->

<!-- wp:buttons {"style":{"spacing":{"margin":{"top":"var:preset|spacing|20"}}}} -->
<div class="wp-block-buttons" style="margin-top:var(--wp--preset--spacing--20)">
<!-- wp:button {"className":"ombra-button-light"} -->
<div class="wp-block-button ombra-button-light"><a class="wp-block-button__link wp-element-button" href="<?php echo esc_url( ombra_category_url( 'candles' ) ); ?>"><?php esc_html_e( 'Shop candles', 'ombra' ); ?></a></div>
<!-- /wp:button -->

<!-- wp:button {"className":"is-style-outline ombra-button-ghost"} -->
<div class="wp-block-button is-style-outline ombra-button-ghost"><a class="wp-block-button__link wp-element-button" href="#scents"><?php esc_html_e( 'Find your scent', 'ombra' ); ?></a></div>
<!-- /wp:button -->
</div>
<!-- /wp:buttons -->
</div>
<!-- /wp:group -->
</div></div>
<!-- /wp:cover -->
