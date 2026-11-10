<?php
/**
 * Title: Footer
 * Slug: ombra/footer
 * Categories: footer
 * Block Types: core/template-part/footer
 * Inserter: no
 *
 * @package Ombra
 */

$ombra_links = array(
	__( 'Shop', 'ombra' ) => array(
		__( 'Candles', 'ombra' )           => ombra_category_url( 'candles' ),
		__( 'Diffusers + sprays', 'ombra' ) => ombra_category_url( 'diffusers-sprays' ),
		__( 'Accessories', 'ombra' )       => ombra_category_url( 'accessories' ),
		__( 'Gift sets', 'ombra' )         => ombra_category_url( 'gift-sets' ),
	),
	__( 'Help', 'ombra' ) => array(
		__( 'Candle care', 'ombra' )        => ombra_page_url( 'candle-care' ),
		__( 'Shipping + returns', 'ombra' ) => ombra_page_url( 'shipping-returns' ),
		__( 'FAQ', 'ombra' )                => ombra_page_url( 'faq' ),
		__( 'Contact', 'ombra' )            => ombra_page_url( 'contact' ),
	),
	__( 'Ombra', 'ombra' ) => array(
		__( 'Our story', 'ombra' )  => ombra_page_url( 'our-story' ),
		__( 'My account', 'ombra' ) => function_exists( 'wc_get_page_permalink' ) ? wc_get_page_permalink( 'myaccount' ) : home_url( '/' ),
	),
);
?>
<!-- wp:group {"className":"ombra-footer","style":{"spacing":{"padding":{"top":"var:preset|spacing|60","bottom":"var:preset|spacing|40"},"blockGap":"var:preset|spacing|50"},"elements":{"link":{"color":{"text":"var:preset|color|base"}}}},"backgroundColor":"night","textColor":"base-3","layout":{"type":"constrained"}} -->
<div class="wp-block-group ombra-footer has-base-3-color has-night-background-color has-text-color has-background has-link-color" style="padding-top:var(--wp--preset--spacing--60);padding-bottom:var(--wp--preset--spacing--40)">
<!-- wp:columns {"align":"wide","style":{"spacing":{"blockGap":{"left":"var:preset|spacing|50"}}}} -->
<div class="wp-block-columns alignwide">
<!-- wp:column {"width":"38%"} -->
<div class="wp-block-column" style="flex-basis:38%">
<!-- wp:site-title {"level":0,"className":"ombra-wordmark ombra-wordmark--footer"} /-->

<!-- wp:paragraph {"style":{"typography":{"lineHeight":"1.5"}},"fontSize":"large","fontFamily":"fraunces"} -->
<p class="has-fraunces-font-family has-large-font-size" style="line-height:1.5"><?php esc_html_e( 'Candles and home fragrance, poured by hand in small batches. Light for the hour after dusk.', 'ombra' ); ?></p>
<!-- /wp:paragraph -->
</div>
<!-- /wp:column -->

<?php foreach ( $ombra_links as $ombra_heading => $ombra_items ) : ?>
<!-- wp:column -->
<div class="wp-block-column">
<!-- wp:heading {"level":2,"className":"ombra-eyebrow","textColor":"base"} -->
<h2 class="wp-block-heading ombra-eyebrow has-base-color has-text-color"><?php echo esc_html( $ombra_heading ); ?></h2>
<!-- /wp:heading -->

<!-- wp:list {"className":"ombra-footer__links is-style-no-bullets"} -->
<ul class="wp-block-list ombra-footer__links is-style-no-bullets">
<?php foreach ( $ombra_items as $ombra_label => $ombra_url ) : ?>
<!-- wp:list-item -->
<li><a href="<?php echo esc_url( $ombra_url ); ?>"><?php echo esc_html( $ombra_label ); ?></a></li>
<!-- /wp:list-item -->
<?php endforeach; ?>
</ul>
<!-- /wp:list -->
</div>
<!-- /wp:column -->
<?php endforeach; ?>
</div>
<!-- /wp:columns -->

<!-- wp:separator {"align":"wide","className":"is-style-wide ombra-footer__rule"} -->
<hr class="wp-block-separator alignwide has-alpha-channel-opacity is-style-wide ombra-footer__rule"/>
<!-- /wp:separator -->

<!-- wp:group {"align":"wide","layout":{"type":"flex","flexWrap":"wrap","justifyContent":"space-between"}} -->
<div class="wp-block-group alignwide">
<!-- wp:paragraph {"fontSize":"x-small"} -->
<p class="has-x-small-font-size"><?php echo esc_html( sprintf( /* translators: %s: year */ __( '© %s Ombra', 'ombra' ), gmdate( 'Y' ) ) ); ?></p>
<!-- /wp:paragraph -->

<!-- wp:paragraph {"fontSize":"x-small"} -->
<p class="has-x-small-font-size"><?php esc_html_e( 'Ombra is a made-up brand for a WooCommerce portfolio demo. Orders here are not real and nothing is charged.', 'ombra' ); ?></p>
<!-- /wp:paragraph -->
</div>
<!-- /wp:group -->
</div>
<!-- /wp:group -->
<?php if ( get_option( 'ombra_demo_mode' ) && current_user_can( 'manage_woocommerce' ) ) : ?>
<!-- wp:paragraph {"className":"ombra-demo-note","fontSize":"x-small"} -->
<p class="ombra-demo-note has-x-small-font-size"><?php esc_html_e( 'Demo admin:', 'ombra' ); ?> <a href="<?php echo esc_url( admin_url( 'admin.php?page=wc-settings&tab=ombra' ) ); ?>"><?php esc_html_e( 'Ombra settings', 'ombra' ); ?></a> · <a href="<?php echo esc_url( admin_url( 'edit.php?post_type=product' ) ); ?>"><?php esc_html_e( 'Products', 'ombra' ); ?></a> · <a href="<?php echo esc_url( admin_url( 'admin.php?page=wc-orders' ) ); ?>"><?php esc_html_e( 'Orders', 'ombra' ); ?></a></p>
<!-- /wp:paragraph -->
<?php endif; ?>
